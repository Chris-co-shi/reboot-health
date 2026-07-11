import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from agent.models import ModelMessage, ModelOptions, ModelResponse, ModelToolCall, ModelToolDefinition
from agent.runtime.confirmation import ConfirmationDecision, ConfirmationDecisionType
from agent.runtime.confirmation_coordinator import ConfirmationCoordinator, TOOL_REJECTED_BY_USER
from agent.runtime.continuation import AgentContinuation
from agent.runtime.generic_loop import (
    ERROR_MAX_MODEL_TURNS_REACHED,
    ERROR_MAX_TOOL_CALLS_REACHED,
    ERROR_SESSION_ALREADY_RUNNING,
    ERROR_SESSION_CONTINUATION_INVALID,
    ERROR_SESSION_MESSAGE_HISTORY_INVALID,
    ERROR_SESSION_NOT_FOUND,
    ERROR_SESSION_NOT_RESUMABLE,
    ERROR_SESSION_STILL_WAITING_CONFIRMATION,
    ERROR_TIMEOUT_REACHED,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_FAILED,
    GENERIC_STATUS_LIMIT_REACHED,
    GENERIC_STATUS_WAITING_CONFIRMATION,
    AgentRequest,
    GenericAgentLoop,
    GenericLoopLimits,
)
from agent.runtime.pending_action import PendingAction
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.runtime.result import AgentRunResult
from agent.runtime.session import AgentSession, AgentSessionStatus, InMemorySessionStore
from agent.tools.contract import ToolDefinition, ToolExecutionResult, ToolPermission, error_content, success_content
from agent.tools.registry import ToolRegistry
from tests.support.scripted_model_provider import ScriptedModelProvider


CONFIRMATION_TOOL_NAME = "record_weight_measurement"
READ_ONLY_TOOL_NAME = "lookup_profile_metric"


class GenericAgentLoopResumeTest(unittest.TestCase):
    """确认完成后的 Resume Agent Loop 行为。"""

    def test_approved_action_resumes_remaining_tool_calls_then_final(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
                        _read_only_tool_call({"value": 7}, "read-2"),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="已记录并读取。", finish_reason="stop"),
            ]
        )
        loop, registry = _loop(
            provider,
            calls,
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-1"],
        )

        paused = loop.run(AgentRequest("记录体重并读取指标", session_id="session-1"))
        _coordinator(session_store, pending_store, registry).resolve(
            ConfirmationDecision(
                session_id=paused.session_id,
                action_id="action-1",
                decision=ConfirmationDecisionType.APPROVE,
            )
        )
        resumed = loop.resume(paused.session_id)

        self.assertEqual(resumed.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(resumed.model_turns, 2)
        self.assertEqual(resumed.tool_calls, 2)
        self.assertEqual(calls, {"confirmation": 1, "read": 1})
        self.assertEqual([message.role for message in resumed.messages], ["system", "user", "assistant", "tool", "tool", "assistant"])
        self.assertEqual([message.role for message in provider.calls[1]["messages"]], ["system", "user", "assistant", "tool", "tool"])
        self.assertEqual([message.role for message in session_store.get("session-1").messages], ["system", "user", "assistant", "tool", "tool", "assistant"])
        self.assertEqual([message.role for message in provider.calls[1]["messages"]].count("user"), 1)
        completed_session = session_store.get("session-1")
        self.assertEqual(completed_session.status, AgentSessionStatus.COMPLETED)
        self.assertIsNone(completed_session.active_run_id)
        self.assertIsNone(completed_session.continuation)
        self.assertNotEqual(paused.run_id, resumed.run_id)
        step_names = [step["name"] for step in resumed.trace.steps]
        self.assertIn("resume_started", step_names)
        self.assertIn("tool_call_resumed", step_names)
        self.assertIn("model_turn_started", step_names)
        self.assertIn("run_finished", step_names)
        self.assertNotIn("activeRunId", json.dumps(resumed.to_dict(), ensure_ascii=False))

    def test_rejected_action_resumes_without_executing_rejected_handler(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="已说明未执行记录。", finish_reason="stop"),
            ]
        )
        loop, registry = _loop(
            provider,
            calls,
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-1"],
        )

        paused = loop.run(AgentRequest("记录体重", session_id="session-1"))
        _coordinator(session_store, pending_store, registry).resolve(
            ConfirmationDecision(
                session_id=paused.session_id,
                action_id="action-1",
                decision=ConfirmationDecisionType.REJECT,
            )
        )
        resumed = loop.resume(paused.session_id)

        self.assertEqual(resumed.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(resumed.model_turns, 2)
        self.assertEqual(resumed.tool_calls, 1)
        self.assertEqual(calls["confirmation"], 0)
        tool_payload = json.loads(provider.calls[1]["messages"][-1].content)
        self.assertEqual(tool_payload["error"]["code"], TOOL_REJECTED_BY_USER)
        self.assertEqual([message.role for message in resumed.messages], ["system", "user", "assistant", "tool", "assistant"])

    def test_resume_pauses_again_on_second_confirmation_tool_without_calling_model(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
                        _confirmation_tool_call({"value": 96, "unit": "kg"}, "confirm-2"),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )
        loop, registry = _loop(
            provider,
            calls,
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-1", "action-2"],
        )

        paused = loop.run(AgentRequest("连续记录体重", session_id="session-1"))
        _coordinator(session_store, pending_store, registry).resolve(
            ConfirmationDecision(
                session_id=paused.session_id,
                action_id="action-1",
                decision=ConfirmationDecisionType.APPROVE,
            )
        )
        resumed = loop.resume(paused.session_id)

        self.assertEqual(resumed.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(resumed.model_turns, 1)
        self.assertEqual(resumed.tool_calls, 1)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(calls["confirmation"], 1)
        waiting_session = session_store.get("session-1")
        self.assertEqual(waiting_session.status, AgentSessionStatus.WAITING_CONFIRMATION)
        self.assertIsNone(waiting_session.active_run_id)
        self.assertEqual(waiting_session.continuation.next_tool_call_index, 1)
        self.assertEqual(waiting_session.continuation.tool_calls_used, 1)
        second_action = pending_store.get("action-2")
        self.assertEqual(second_action.originating_run_id, paused.run_id)
        self.assertEqual(second_action.tool_call_index, 1)
        self.assertEqual([message.role for message in waiting_session.messages], ["system", "user", "assistant", "tool"])

    def test_new_model_turn_confirmation_uses_resume_run_id(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call({"value": 96, "unit": "kg"}, "confirm-new"),
                    ),
                    finish_reason="tool_calls",
                ),
            ]
        )
        loop, registry = _loop(
            provider,
            calls,
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-1", "action-2"],
        )

        paused = loop.run(AgentRequest("记录后继续判断", session_id="session-1"))
        _coordinator(session_store, pending_store, registry).resolve(
            ConfirmationDecision(
                session_id=paused.session_id,
                action_id="action-1",
                decision=ConfirmationDecisionType.APPROVE,
            )
        )
        resumed = loop.resume(paused.session_id)

        self.assertEqual(resumed.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(resumed.model_turns, 2)
        self.assertEqual(resumed.tool_calls, 1)
        self.assertEqual(pending_store.get("action-2").originating_run_id, resumed.run_id)
        self.assertEqual(session_store.get("session-1").continuation.model_turns_used, 2)
        self.assertEqual([message.role for message in session_store.get("session-1").messages], ["system", "user", "assistant", "tool", "assistant"])

    def test_resume_timeout_with_zero_remaining_runtime_calls_nothing(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        session_store.create(_active_resumable_session(remaining_runtime_seconds=0.0))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop, _ = _loop(
            provider,
            calls,
            session_store=session_store,
            pending_store=pending_store,
            monotonic_provider=ControlledClock([100, 100]),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_TIMEOUT_REACHED)
        self.assertEqual(len(provider.calls), 0)
        failed_session = session_store.get("session-1")
        self.assertEqual(failed_session.status, AgentSessionStatus.FAILED)
        self.assertIsNone(failed_session.active_run_id)

    def test_tool_budget_is_not_reset_on_resume(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        session_store.create(_active_resumable_two_tool_session())
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop, _ = _loop(
            provider,
            calls,
            session_store=session_store,
            limits=GenericLoopLimits(max_tool_calls=1),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_MAX_TOOL_CALLS_REACHED)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(calls, {"confirmation": 0, "read": 0})

    def test_resume_pause_saves_new_remaining_runtime_seconds(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        session_store.create(_active_resumable_two_confirmation_session())
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop, _ = _loop(
            provider,
            calls,
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-2"],
            monotonic_provider=ControlledClock([100, 105, 110, 112, 112]),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(session_store.get("session-1").continuation.remaining_runtime_seconds, 8)

    def test_resume_preconditions_fail_without_model_or_tool_calls(self) -> None:
        cases = [
            ("missing", None, ERROR_SESSION_NOT_FOUND),
            ("waiting", _waiting_session(), ERROR_SESSION_STILL_WAITING_CONFIRMATION),
            ("running", _active_resumable_session(status=AgentSessionStatus.RUNNING, active_run_id="run-x"), ERROR_SESSION_ALREADY_RUNNING),
            ("no-continuation", AgentSession(session_id="session-1"), ERROR_SESSION_NOT_RESUMABLE),
            ("pending-pointer", _active_resumable_session(pending_action_id="action-1"), ERROR_SESSION_STILL_WAITING_CONFIRMATION),
            ("bad-index", _active_resumable_session(assistant_message_index=99), ERROR_SESSION_CONTINUATION_INVALID),
            ("missing-tool-result", _active_resumable_session(include_tool_result=False), ERROR_SESSION_MESSAGE_HISTORY_INVALID),
        ]
        for name, session, error_code in cases:
            with self.subTest(name=name):
                calls = {"confirmation": 0, "read": 0}
                session_store = InMemorySessionStore()
                if session is not None:
                    session_store.create(session)
                provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
                loop, _ = _loop(provider, calls, session_store=session_store)

                result = loop.resume("session-1")

                self.assertEqual(result.status, GENERIC_STATUS_FAILED)
                self.assertEqual(result.error.code, error_code)
                self.assertEqual(len(provider.calls), 0)
                self.assertEqual(calls, {"confirmation": 0, "read": 0})

    def test_model_budget_is_not_reset_on_resume(self) -> None:
        calls = {"confirmation": 0, "read": 0}
        session_store = InMemorySessionStore()
        session_store.create(_active_resumable_session(model_turns_used=1))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop, _ = _loop(
            provider,
            calls,
            session_store=session_store,
            limits=GenericLoopLimits(max_model_turns=1),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_MAX_MODEL_TURNS_REACHED)
        self.assertEqual(len(provider.calls), 0)


class GenericAgentLoopResumeConcurrencyTest(unittest.TestCase):
    """RUNNING 占用避免同一 Session 被重复执行。"""

    def test_concurrent_resume_claim_allows_only_one_provider_call(self) -> None:
        session_store = InMemorySessionStore()
        session_store.create(_active_resumable_session())
        provider = BlockingProvider(ModelResponse(content="完成", finish_reason="stop"))
        loop, _ = _loop(
            provider,
            {"confirmation": 0, "read": 0},
            session_store=session_store,
        )

        first_result: list[AgentRunResult] = []
        thread = threading.Thread(target=lambda: first_result.append(loop.resume("session-1")))
        thread.start()
        self.assertTrue(provider.entered.wait(2))

        second = loop.resume("session-1")
        provider.release.set()
        thread.join(2)

        self.assertEqual(second.status, GENERIC_STATUS_FAILED)
        self.assertEqual(second.error.code, ERROR_SESSION_ALREADY_RUNNING)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(first_result[0].status, GENERIC_STATUS_COMPLETED)
        self.assertIsNone(session_store.get("session-1").active_run_id)

    def test_concurrent_fresh_run_claim_allows_only_one_provider_call(self) -> None:
        session_store = InMemorySessionStore()
        session_store.create(AgentSession(session_id="session-1"))
        provider = BlockingProvider(ModelResponse(content="完成", finish_reason="stop"))
        loop, _ = _loop(
            provider,
            {"confirmation": 0, "read": 0},
            session_store=session_store,
        )

        first_result: list[AgentRunResult] = []
        thread = threading.Thread(
            target=lambda: first_result.append(
                loop.run(AgentRequest("任务一", session_id="session-1"))
            )
        )
        thread.start()
        self.assertTrue(provider.entered.wait(2))

        second = loop.run(AgentRequest("任务二", session_id="session-1"))
        provider.release.set()
        thread.join(2)

        self.assertEqual(second.status, GENERIC_STATUS_FAILED)
        self.assertEqual(second.error.code, ERROR_SESSION_ALREADY_RUNNING)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(first_result[0].status, GENERIC_STATUS_COMPLETED)
        self.assertIsNone(session_store.get("session-1").active_run_id)


class ControlledClock:
    """按顺序返回 monotonic 时间。"""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self._last = values[-1] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


class BlockingProvider:
    """阻塞在 complete_turn 内，用于验证 RUNNING claim。"""

    provider_name = "blocking"

    def __init__(self, response: ModelResponse) -> None:
        self.response = response
        self.calls: list[tuple[ModelMessage, ...]] = []
        self.entered = threading.Event()
        self.release = threading.Event()

    def complete_turn(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition] = (),
        options: ModelOptions | None = None,
    ) -> ModelResponse:
        self.calls.append(tuple(messages))
        self.entered.set()
        self.release.wait(5)
        return self.response


def _loop(
    provider,
    calls: dict[str, int],
    *,
    session_store: InMemorySessionStore | None = None,
    pending_store: InMemoryPendingActionStore | None = None,
    action_ids: list[str] | None = None,
    limits: GenericLoopLimits | None = None,
    monotonic_provider=None,
) -> tuple[GenericAgentLoop, ToolRegistry]:
    """创建共享 Store 的测试 Loop。"""

    ids = list(action_ids or ["action-default"])

    def next_action_id() -> str:
        return ids.pop(0)

    registry = _registry(calls)
    loop = GenericAgentLoop(
        provider=provider,
        limits=limits,
        session_store=session_store or InMemorySessionStore(),
        pending_action_store=pending_store or InMemoryPendingActionStore(),
        now_provider=_fixed_now,
        tool_registry=registry,
        action_id_factory=next_action_id,
        monotonic_provider=monotonic_provider,
    )
    return loop, registry


def _coordinator(
    session_store: InMemorySessionStore,
    pending_store: InMemoryPendingActionStore,
    registry: ToolRegistry,
) -> ConfirmationCoordinator:
    """创建与 Loop 共用 Store/Registry 的确认协调器。"""

    return ConfirmationCoordinator(
        session_store=session_store,
        pending_action_store=pending_store,
        tool_registry=registry,
        now_provider=_fixed_now,
    )


def _registry(calls: dict[str, int]) -> ToolRegistry:
    return ToolRegistry([_read_only_tool(calls), _confirmation_tool(calls)])


def _confirmation_tool(calls: dict[str, int]) -> ToolDefinition:
    """确认型测试工具：只允许 ApprovedActionExecutor 调用。"""

    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls["confirmation"] += 1
        return {"recorded": True, "value": arguments["value"]}

    return ToolDefinition(
        name=CONFIRMATION_TOOL_NAME,
        description="Record a weight measurement after confirmation",
        permission=ToolPermission.CONFIRMATION_REQUIRED,
        input_schema={"type": "object"},
        handler=handler,
    )


def _read_only_tool(calls: dict[str, int]) -> ToolDefinition:
    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls["read"] += 1
        return {"value": arguments["value"]}

    return ToolDefinition(
        name=READ_ONLY_TOOL_NAME,
        description="Read a metric",
        input_schema={"type": "object"},
        handler=handler,
    )


def _confirmation_tool_call(arguments: Mapping[str, Any], id: str) -> ModelToolCall:
    return _tool_call(id=id, name=CONFIRMATION_TOOL_NAME, arguments=arguments)


def _read_only_tool_call(arguments: Mapping[str, Any], id: str) -> ModelToolCall:
    return _tool_call(id=id, name=READ_ONLY_TOOL_NAME, arguments=arguments)


def _tool_call(id: str, name: str, arguments: Mapping[str, Any]) -> ModelToolCall:
    return ModelToolCall(
        id=id,
        name=name,
        raw_arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        arguments=arguments,
    )


def _active_resumable_session(
    *,
    status: AgentSessionStatus = AgentSessionStatus.ACTIVE,
    active_run_id: str | None = None,
    pending_action_id: str | None = None,
    assistant_message_index: int = 2,
    model_turns_used: int = 1,
    remaining_runtime_seconds: float = 30.0,
    include_tool_result: bool = True,
) -> AgentSession:
    """构造“确认已处理、等待 resume”的 Session。"""

    started_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    messages = [
        ModelMessage(role="system", content="system"),
        ModelMessage(role="user", content="记录体重"),
        ModelMessage(
            role="assistant",
            tool_calls=(
                _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
            ),
        ),
    ]
    if include_tool_result:
        messages.append(
            ModelMessage(
                role="tool",
                name=CONFIRMATION_TOOL_NAME,
                tool_call_id="confirm-1",
                content=success_content({"recorded": True}),
            )
        )
    return AgentSession(
        session_id="session-1",
        status=status,
        messages=messages,
        pending_action_id=pending_action_id,
        active_run_id=active_run_id,
        run_fence_generation=1 if status == AgentSessionStatus.RUNNING else 0,
        active_run_last_heartbeat_at=(
            started_at if status == AgentSessionStatus.RUNNING else None
        ),
        active_run_lease_expires_at=(
            started_at + timedelta(seconds=60)
            if status == AgentSessionStatus.RUNNING
            else None
        ),
        continuation=AgentContinuation(
            originating_run_id="run-original",
            assistant_message_index=assistant_message_index,
            next_tool_call_index=1,
            model_turns_used=model_turns_used,
            tool_calls_used=1,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
            remaining_runtime_seconds=remaining_runtime_seconds,
        ),
    )


def _active_resumable_two_tool_session() -> AgentSession:
    """构造还有一个 read-only Tool 待处理、但工具预算已用完的 Session。"""

    started_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.ACTIVE,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="记录体重并读取指标"),
            ModelMessage(
                role="assistant",
                tool_calls=(
                    _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
                    _read_only_tool_call({"value": 7}, "read-2"),
                ),
            ),
            ModelMessage(
                role="tool",
                name=CONFIRMATION_TOOL_NAME,
                tool_call_id="confirm-1",
                content=success_content({"recorded": True}),
            ),
        ],
        continuation=AgentContinuation(
            originating_run_id="run-original",
            assistant_message_index=2,
            next_tool_call_index=1,
            model_turns_used=1,
            tool_calls_used=1,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
            remaining_runtime_seconds=30,
        ),
    )


def _active_resumable_two_confirmation_session() -> AgentSession:
    """构造第二个 confirmation Tool 等待 Resume 发现的 Session。"""

    started_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.ACTIVE,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="连续记录体重"),
            ModelMessage(
                role="assistant",
                tool_calls=(
                    _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
                    _confirmation_tool_call({"value": 96, "unit": "kg"}, "confirm-2"),
                ),
            ),
            ModelMessage(
                role="tool",
                name=CONFIRMATION_TOOL_NAME,
                tool_call_id="confirm-1",
                content=success_content({"recorded": True}),
            ),
        ],
        continuation=AgentContinuation(
            originating_run_id="run-original",
            assistant_message_index=2,
            next_tool_call_index=1,
            model_turns_used=1,
            tool_calls_used=1,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
            remaining_runtime_seconds=20,
        ),
    )


def _waiting_session() -> AgentSession:
    started_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.WAITING_CONFIRMATION,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="记录体重"),
            ModelMessage(
                role="assistant",
                tool_calls=(
                    _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
                ),
            ),
        ],
        pending_action_id="action-1",
        continuation=AgentContinuation(
            originating_run_id="run-original",
            assistant_message_index=2,
            next_tool_call_index=0,
            model_turns_used=1,
            tool_calls_used=0,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
        ),
    )


def _pending_action() -> PendingAction:
    created_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    return PendingAction(
        action_id="action-1",
        session_id="session-1",
        originating_run_id="run-original",
        tool_call_id="confirm-1",
        tool_name=CONFIRMATION_TOOL_NAME,
        arguments={"value": 95, "unit": "kg"},
        assistant_message_index=2,
        tool_call_index=0,
        summary="pending",
        created_at=created_at,
        updated_at=created_at,
        expires_at=created_at + timedelta(minutes=15),
        result_content=success_content({"recorded": True}),
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=8)))


if __name__ == "__main__":
    unittest.main()
