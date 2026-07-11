import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from agent.models import (
    ModelMessage,
    ModelOptions,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
    ProviderResponseError,
)
from agent.runtime.continuation import AgentContinuation
from agent.runtime.generic_loop import (
    ERROR_MAX_MODEL_TURNS_REACHED,
    ERROR_MAX_TOOL_CALLS_REACHED,
    ERROR_SESSION_FINALIZATION_PERSIST_FAILED,
    ERROR_SESSION_FINALIZATION_STATE_UNKNOWN,
    ERROR_SESSION_OWNERSHIP_LOST,
    ERROR_TIMEOUT_REACHED,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_FAILED,
    GENERIC_STATUS_LIMIT_REACHED,
    AgentRequest,
    GenericAgentLoop,
    GenericLoopLimits,
)
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionStoreError,
    copy_session,
    utc_now,
)
from agent.tools.contract import ToolDefinition, ToolPermission, success_content
from agent.tools.registry import ToolRegistry
from tests.support.scripted_model_provider import ScriptedModelProvider


CONFIRMATION_TOOL_NAME = "record_weight_measurement"
READ_ONLY_TOOL_NAME = "lookup_profile_metric"


class GenericAgentLoopFinalizationFailureTest(unittest.TestCase):
    """Session finalization 保存失败时必须 fail closed，不能伪造业务成功。"""

    def test_final_answer_save_failure_before_commit_returns_finalization_error(self) -> None:
        """终态保存提交前失败时，Store 仍保持 RUNNING，对外返回持久化失败。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.COMPLETED,
            mode=FinalizationFailureMode.FAIL_BEFORE_COMMIT,
        )
        provider = ScriptedModelProvider(
            [ModelResponse(content="完成", finish_reason="stop")]
        )
        loop = _loop(provider, store)

        result = loop.run(AgentRequest("直接完成", session_id="session-1"))

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_PERSIST_FAILED)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(store.finalization_save_attempts, 1)
        stored = store.get("session-1")
        self.assertEqual(stored.status, AgentSessionStatus.RUNNING)
        self.assertEqual(stored.active_run_id, result.run_id)
        self.assertEqual(stored.version, 6)
        self.assertNotIn("private-store-path", json.dumps(result.to_dict(), ensure_ascii=False))

    def test_final_answer_commit_then_raise_returns_original_completed_result(self) -> None:
        """保存已经提交但响应失败时，read-after-failure 读取终态后允许返回原结果。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.COMPLETED,
            mode=FinalizationFailureMode.COMMIT_THEN_RAISE,
        )
        provider = ScriptedModelProvider(
            [ModelResponse(content="完成", finish_reason="stop")]
        )
        loop = _loop(provider, store)

        result = loop.run(AgentRequest("直接完成", session_id="session-1"))

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.final_text, "完成")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(store.finalization_save_attempts, 1)
        stored = store.get("session-1")
        self.assertEqual(stored.status, AgentSessionStatus.COMPLETED)
        self.assertIsNone(stored.active_run_id)
        self.assertEqual(stored.version, 7)

    def test_save_and_read_failure_returns_state_unknown(self) -> None:
        """保存失败后连读取都失败时，Runtime 只能报告终态未知。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.COMPLETED,
            mode=FinalizationFailureMode.SAVE_AND_READ_FAIL,
        )
        provider = ScriptedModelProvider(
            [ModelResponse(content="完成", finish_reason="stop")]
        )
        loop = _loop(provider, store)

        result = loop.run(AgentRequest("直接完成", session_id="session-1"))

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_STATE_UNKNOWN)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(store.finalization_save_attempts, 1)
        stored = store.raw_session("session-1")
        self.assertEqual(stored.status, AgentSessionStatus.RUNNING)
        self.assertEqual(stored.active_run_id, result.run_id)

    def test_ownership_changed_after_save_failure_is_not_overwritten(self) -> None:
        """read-back 发现其他 run 已接管时，当前 run 不得清除新 owner。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.COMPLETED,
            mode=FinalizationFailureMode.OWNERSHIP_CHANGED,
            owner_after_failure="run-other",
        )
        provider = ScriptedModelProvider(
            [ModelResponse(content="完成", finish_reason="stop")]
        )
        loop = _loop(provider, store)

        result = loop.run(AgentRequest("直接完成", session_id="session-1"))

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_OWNERSHIP_LOST)
        self.assertEqual(len(provider.calls), 1)
        stored = store.raw_session("session-1")
        self.assertEqual(stored.status, AgentSessionStatus.RUNNING)
        self.assertEqual(stored.active_run_id, "run-other")
        self.assertEqual(stored.version, 7)

    def test_second_confirmation_pause_save_failure_returns_finalization_error(self) -> None:
        """Resume 遇到第二个确认工具时，WAITING_CONFIRMATION 保存失败不得伪装暂停。"""

        calls = {"confirmation": 0, "read": 0}
        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.WAITING_CONFIRMATION,
            mode=FinalizationFailureMode.FAIL_BEFORE_COMMIT,
        )
        store.create(_active_resumable_two_confirmation_session())
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(
            provider,
            store,
            pending_store=pending_store,
            calls=calls,
            action_ids=["action-2"],
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_PERSIST_FAILED)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(calls, {"confirmation": 0, "read": 0})
        self.assertIsNotNone(pending_store.get("action-2"))
        stored = store.get("session-1")
        self.assertEqual(stored.status, AgentSessionStatus.RUNNING)
        self.assertEqual(stored.active_run_id, result.run_id)
        self.assertIsNone(stored.pending_action_id)

    def test_timeout_save_failure_returns_finalization_error_without_model_or_tool(self) -> None:
        """active runtime 已耗尽时，FAILED 保存失败不得返回普通 timeout limit。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.FAILED,
            mode=FinalizationFailureMode.FAIL_BEFORE_COMMIT,
        )
        store.create(_active_resumable_session(remaining_runtime_seconds=0.0))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(
            provider,
            store,
            monotonic_provider=ControlledClock([100, 100]),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_PERSIST_FAILED)
        self.assertEqual(len(provider.calls), 0)
        self.assertNotEqual(result.error.code, ERROR_TIMEOUT_REACHED)

    def test_model_limit_save_failure_returns_finalization_error(self) -> None:
        """模型回合预算已耗尽时，FAILED 保存失败优先报告 finalization 错误。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.FAILED,
            mode=FinalizationFailureMode.FAIL_BEFORE_COMMIT,
        )
        store.create(_active_resumable_session(model_turns_used=1))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(
            provider,
            store,
            limits=GenericLoopLimits(max_model_turns=1),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_PERSIST_FAILED)
        self.assertEqual(len(provider.calls), 0)
        self.assertNotEqual(result.error.code, ERROR_MAX_MODEL_TURNS_REACHED)

    def test_tool_limit_save_failure_returns_finalization_error_without_handler(self) -> None:
        """工具预算不足时，FAILED 保存失败不得调用剩余工具 handler。"""

        calls = {"confirmation": 0, "read": 0}
        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.FAILED,
            mode=FinalizationFailureMode.FAIL_BEFORE_COMMIT,
        )
        store.create(_active_resumable_two_tool_session())
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(
            provider,
            store,
            calls=calls,
            limits=GenericLoopLimits(max_tool_calls=1),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_PERSIST_FAILED)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(calls, {"confirmation": 0, "read": 0})
        self.assertNotEqual(result.error.code, ERROR_MAX_TOOL_CALLS_REACHED)

    def test_provider_failure_save_failure_returns_finalization_error_without_retry(self) -> None:
        """Provider 已经抛错后，FAILED 保存失败不得再次调用 Provider。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.FAILED,
            mode=FinalizationFailureMode.FAIL_BEFORE_COMMIT,
        )
        provider = FailingProvider()
        loop = _loop(provider, store)

        result = loop.run(AgentRequest("触发 provider 错误", session_id="session-1"))

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_PERSIST_FAILED)
        self.assertEqual(len(provider.calls), 1)
        self.assertNotIn("private-store-path", json.dumps(result.to_dict(), ensure_ascii=False))

    def test_limit_commit_then_raise_returns_original_limit_result(self) -> None:
        """FAILED 终止态已提交但响应失败时，仍可返回原始 limit 结果。"""

        store = FinalizationFailureSessionStore(
            target_status=AgentSessionStatus.FAILED,
            mode=FinalizationFailureMode.COMMIT_THEN_RAISE,
        )
        store.create(_active_resumable_session(model_turns_used=1))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(
            provider,
            store,
            limits=GenericLoopLimits(max_model_turns=1),
        )

        result = loop.resume("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_MAX_MODEL_TURNS_REACHED)
        self.assertEqual(len(provider.calls), 0)
        stored = store.get("session-1")
        self.assertEqual(stored.status, AgentSessionStatus.FAILED)
        self.assertIsNone(stored.active_run_id)


class FinalizationFailureMode:
    """测试 Store 的失败模式枚举，使用字符串避免引入生产依赖。"""

    FAIL_BEFORE_COMMIT = "fail_before_commit"
    COMMIT_THEN_RAISE = "commit_then_raise"
    SAVE_AND_READ_FAIL = "save_and_read_fail"
    OWNERSHIP_CHANGED = "ownership_changed"


class FinalizationFailureSessionStore(InMemorySessionStore):
    """只在目标 finalization 保存时制造失败窗口的测试 Store。

    普通 claim、消息追加和 tool result 保存都交给 InMemorySessionStore；只有当
    Runtime 尝试把当前 RUNNING session 保存为目标终态且 owner 已清空时才触发。
    这样测试能精确覆盖 finalization 释放边界，而不会干扰前置执行路径。
    """

    def __init__(
        self,
        *,
        target_status: AgentSessionStatus,
        mode: str,
        owner_after_failure: str = "run-other",
    ) -> None:
        super().__init__()
        self.target_status = target_status
        self.mode = mode
        self.owner_after_failure = owner_after_failure
        self.finalization_save_attempts = 0
        self.fail_reads = False

    def save(self, session: AgentSession, expected_version: int) -> AgentSession:
        if not self._is_target_finalization(session):
            return super().save(session, expected_version)

        self.finalization_save_attempts += 1
        if self.mode == FinalizationFailureMode.FAIL_BEFORE_COMMIT:
            raise SessionStoreError("private-store-path: save failed before commit")
        if self.mode == FinalizationFailureMode.COMMIT_THEN_RAISE:
            super().save(session, expected_version)
            raise SessionStoreError("private-store-path: ack lost after commit")
        if self.mode == FinalizationFailureMode.SAVE_AND_READ_FAIL:
            self.fail_reads = True
            raise SessionStoreError("private-store-path: save and read failed")
        if self.mode == FinalizationFailureMode.OWNERSHIP_CHANGED:
            self._change_owner(session.session_id)
            raise SessionStoreError("private-store-path: owner changed")
        raise AssertionError(f"Unsupported failure mode: {self.mode}")

    def get(self, session_id: str) -> AgentSession | None:
        if self.fail_reads:
            raise SessionStoreError("private-store-path: read failed")
        return super().get(session_id)

    def raw_session(self, session_id: str) -> AgentSession:
        """绕过故障注入读取 Store 内部快照，只用于断言失败后的真实状态。"""

        with self._lock:
            session = self._sessions[session_id]
            return copy_session(session)

    def _is_target_finalization(self, session: AgentSession) -> bool:
        return (
            session.status == self.target_status
            and session.active_run_id is None
        )

    def _change_owner(self, session_id: str) -> None:
        """模拟保存失败窗口中另一个执行者推进 version 并接管 ownership。"""

        with self._lock:
            current = self._sessions[session_id]
            changed = copy_session(current)
            changed.status = AgentSessionStatus.RUNNING
            changed.active_run_id = self.owner_after_failure
            changed.updated_at = utc_now()
            self._sessions[session_id] = replace(
                changed,
                version=current.version + 1,
            )


class FailingProvider:
    """抛出 ProviderResponseError 的测试 Provider，并记录调用次数。"""

    provider_name = "failing-provider"

    def __init__(self) -> None:
        self.calls: list[tuple[ModelMessage, ...]] = []

    def complete_turn(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition] = (),
        options: ModelOptions | None = None,
    ) -> ModelResponse:
        self.calls.append(tuple(messages))
        raise ProviderResponseError(
            "private-store-path: provider failed",
            safe_summary="Provider response could not be used.",
        )


class ControlledClock:
    """按顺序返回 monotonic 时间，用于稳定触发 active runtime timeout。"""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self._last = values[-1] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


def _loop(
    provider,
    session_store: InMemorySessionStore,
    *,
    pending_store: InMemoryPendingActionStore | None = None,
    calls: dict[str, int] | None = None,
    action_ids: list[str] | None = None,
    limits: GenericLoopLimits | None = None,
    monotonic_provider=None,
) -> GenericAgentLoop:
    """创建带共享 Store 的 GenericAgentLoop，避免测试误用产品 Bootstrap。"""

    ids = list(action_ids or ["action-default"])

    def next_action_id() -> str:
        return ids.pop(0)

    return GenericAgentLoop(
        provider=provider,
        limits=limits,
        session_store=session_store,
        pending_action_store=pending_store or InMemoryPendingActionStore(),
        now_provider=_fixed_now,
        tool_registry=_registry(calls or {"confirmation": 0, "read": 0}),
        action_id_factory=next_action_id,
        monotonic_provider=monotonic_provider,
    )


def _registry(calls: dict[str, int]) -> ToolRegistry:
    return ToolRegistry([_read_only_tool(calls), _confirmation_tool(calls)])


def _confirmation_tool(calls: dict[str, int]) -> ToolDefinition:
    """确认型工具：普通 Runtime 只能暂停，不能直接调用 handler。"""

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
    """只读测试工具，用于验证 finalization 失败后不会重复执行副作用。"""

    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls["read"] += 1
        return {"value": arguments["value"]}

    return ToolDefinition(
        name=READ_ONLY_TOOL_NAME,
        description="Read a metric",
        input_schema={"type": "object"},
        handler=handler,
    )


def _active_resumable_session(
    *,
    model_turns_used: int = 1,
    remaining_runtime_seconds: float = 30.0,
) -> AgentSession:
    """构造已写入确认结果、等待 resume 的单工具 Session。"""

    started_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.ACTIVE,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="记录体重"),
            ModelMessage(
                role="assistant",
                tool_calls=(
                    _confirmation_tool_call({"value": 95, "unit": "kg"}, "confirm-1"),
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
            model_turns_used=model_turns_used,
            tool_calls_used=1,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
            remaining_runtime_seconds=remaining_runtime_seconds,
        ),
    )


def _active_resumable_two_tool_session() -> AgentSession:
    """构造还有一个 read-only Tool 未处理、但剩余工具预算不足的 Session。"""

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
    """构造第一个确认已完成、第二个确认等待 resume 发现的 Session。"""

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


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=8)))


if __name__ == "__main__":
    unittest.main()
