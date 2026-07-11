import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from agent.models import ModelResponse
from agent.runtime.generic_loop import (
    ERROR_SESSION_ALREADY_RUNNING,
    ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY,
    AgentRequest,
    GenericAgentLoop,
    GenericLoopLimits,
)
from agent.runtime.run_ownership import RunOwnership
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionRunFenceLostError,
    SessionRunLeaseExpiredError,
)
from tests.support.scripted_model_provider import ScriptedModelProvider


class RunLeaseAndFencingTest(unittest.TestCase):
    """RUNNING lease、heartbeat 与 generation fencing 的核心合同。"""

    def test_successful_run_releases_lease_but_keeps_generation(self) -> None:
        store = InMemorySessionStore()
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])
        loop = _loop(provider, store)

        result = loop.run(AgentRequest("直接完成", session_id="session-1"))
        stored = store.get(result.session_id)

        self.assertEqual(stored.status, AgentSessionStatus.COMPLETED)
        self.assertEqual(stored.run_fence_generation, 1)
        self.assertIsNone(stored.active_run_id)
        self.assertIsNone(stored.active_run_last_heartbeat_at)
        self.assertIsNone(stored.active_run_lease_expires_at)

    def test_valid_running_session_blocks_without_model_call(self) -> None:
        store = InMemorySessionStore()
        store.create(_running_session(lease_expires_at=_fixed_now() + timedelta(seconds=60)))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(provider, store)

        result = loop.run(AgentRequest("新任务", session_id="session-1"))

        self.assertEqual(result.error.code, ERROR_SESSION_ALREADY_RUNNING)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(store.get("session-1").active_run_id, "run-1")

    def test_expired_running_session_requires_recovery_without_takeover(self) -> None:
        store = InMemorySessionStore()
        store.create(_running_session(lease_expires_at=_fixed_now()))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(provider, store, now_provider=_fixed_now)

        result = loop.resume("session-1")
        stored = store.get("session-1")

        self.assertEqual(result.error.code, ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(stored.active_run_id, "run-1")
        self.assertEqual(stored.run_fence_generation, 1)

    def test_heartbeat_extends_only_matching_owner_and_generation(self) -> None:
        store = InMemorySessionStore()
        store.create(_running_session(lease_expires_at=_fixed_now() + timedelta(seconds=60)))
        loop = _loop(ScriptedModelProvider([]), store, now_provider=_later_now)

        refreshed = loop._heartbeat_owned_session(  # noqa: SLF001 - Runtime 内部合同测试。
            RunOwnership("session-1", "run-1", 1)
        )

        self.assertEqual(refreshed.active_run_last_heartbeat_at, _later_now())
        self.assertEqual(
            refreshed.active_run_lease_expires_at,
            _later_now() + timedelta(seconds=90),
        )
        with self.assertRaises(SessionRunFenceLostError):
            loop._heartbeat_owned_session(RunOwnership("session-1", "other", 1))  # noqa: SLF001
        with self.assertRaises(SessionRunFenceLostError):
            loop._heartbeat_owned_session(RunOwnership("session-1", "run-1", 2))  # noqa: SLF001

    def test_expired_owner_cannot_heartbeat(self) -> None:
        store = InMemorySessionStore()
        store.create(_running_session(lease_expires_at=_fixed_now()))
        loop = _loop(ScriptedModelProvider([]), store, now_provider=_later_now)

        with self.assertRaises(SessionRunLeaseExpiredError):
            loop._heartbeat_owned_session(RunOwnership("session-1", "run-1", 1))  # noqa: SLF001

    def test_old_generation_cannot_save_after_new_owner_claims(self) -> None:
        store = InMemorySessionStore()
        old_session = store.create(
            _running_session(lease_expires_at=_fixed_now() + timedelta(seconds=60))
        )
        old_ownership = RunOwnership("session-1", "run-1", 1)
        new_owner = replace(
            store.get("session-1"),
            active_run_id="run-2",
            run_fence_generation=2,
        )
        store.save(new_owner, expected_version=new_owner.version)
        loop = _loop(ScriptedModelProvider([]), store)

        old_session.context_summary = "old write"
        with self.assertRaises(SessionRunFenceLostError):
            loop._save_owned_session(old_session, old_ownership)  # noqa: SLF001

        self.assertEqual(store.get("session-1").active_run_id, "run-2")
        self.assertEqual(store.get("session-1").context_summary, "")

    def test_lease_configuration_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            GenericAgentLoop(
                provider=ScriptedModelProvider([]),
                limits=GenericLoopLimits(timeout_seconds=10),
                run_lease_ttl_seconds=10,
            )
        with self.assertRaises(ValueError):
            GenericAgentLoop(
                provider=ScriptedModelProvider([]),
                limits=GenericLoopLimits(timeout_seconds=10),
                run_lease_ttl_seconds=20,
                run_lease_heartbeat_interval_seconds=20,
            )


def _loop(
    provider: ScriptedModelProvider,
    store: InMemorySessionStore,
    *,
    now_provider=None,
) -> GenericAgentLoop:
    return GenericAgentLoop(
        provider=provider,
        session_store=store,
        now_provider=now_provider or _fixed_now,
        run_lease_ttl_seconds=90,
        run_lease_heartbeat_interval_seconds=10,
        lease_safety_margin_seconds=1,
    )


def _running_session(*, lease_expires_at: datetime) -> AgentSession:
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.RUNNING,
        active_run_id="run-1",
        run_fence_generation=1,
        active_run_last_heartbeat_at=_fixed_now() - timedelta(seconds=1),
        active_run_lease_expires_at=lease_expires_at,
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _later_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 6, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
