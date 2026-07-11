import json
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from agent.models import ModelMessage, ModelResponse, ModelToolCall
from agent.runtime.continuation import AgentContinuation
from agent.runtime.generic_loop import (
    ERROR_SESSION_STATE_CONFLICT,
    ERROR_SESSION_VERSION_CONFLICT,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_FAILED,
    GENERIC_STATUS_WAITING_CONFIRMATION,
    AgentRequest,
    GenericAgentLoop,
    GenericLoopLimits,
)
from agent.runtime.pending_action import PendingAction, calculate_arguments_hash
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionVersionConflictError,
)
from agent.tools.contract import ToolArgumentError, ToolDefinition, ToolPermission
from agent.tools.registry import ToolRegistry
from tests.support.scripted_model_provider import ScriptedModelProvider


class GenericAgentLoopConfirmationPauseTest(unittest.TestCase):
    """GenericAgentLoop 的确认暂停切片行为。

    本文件只验证 Slice 3：遇到合法 confirmation-required Tool Call 时暂停，并把
    PendingAction/Continuation/Session 状态写好。这里不实现、不测试 Approve、
    Reject、Resume 或已批准后的执行入口。
    """

    def test_valid_confirmation_tool_pauses_without_calling_handler(self) -> None:
        handler_calls = {"confirmation": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call(
                            {"value": 95, "unit": "kg"},
                            id="confirm-1",
                        ),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )

        result = _run(
            provider,
            registry=_confirmation_registry(handler_calls),
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-1"],
            limits=GenericLoopLimits(timeout_seconds=42),
            monotonic_provider=ControlledClock([100, 100, 100, 100, 100, 107, 107]),
        )

        self.assertEqual(result.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(result.model_turns, 1)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(handler_calls["confirmation"], 0)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])
        self.assertEqual(result.messages[2].tool_calls[0].id, "confirm-1")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(result.trace.final_outcome, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(result.trace.tool_calls, [])

        loaded_session = session_store.get(result.session_id)
        self.assertEqual(loaded_session.status, AgentSessionStatus.WAITING_CONFIRMATION)
        self.assertEqual(loaded_session.pending_action_id, "action-1")
        self.assertEqual([message.role for message in loaded_session.messages], ["system", "user", "assistant"])
        self.assertIsNotNone(loaded_session.continuation)
        self.assertEqual(loaded_session.continuation.originating_run_id, result.run_id)
        self.assertEqual(loaded_session.continuation.assistant_message_index, 2)
        self.assertEqual(loaded_session.continuation.next_tool_call_index, 0)
        self.assertEqual(loaded_session.continuation.model_turns_used, 1)
        self.assertEqual(loaded_session.continuation.tool_calls_used, 0)
        self.assertEqual(
            loaded_session.continuation.started_at,
            datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(
            loaded_session.continuation.deadline_at,
            datetime(2026, 1, 1, 19, 4, 47, tzinfo=timezone.utc),
        )
        self.assertEqual(loaded_session.continuation.remaining_runtime_seconds, 35)

        loaded_action = pending_store.get("action-1")
        self.assertEqual(loaded_action.session_id, result.session_id)
        self.assertEqual(loaded_action.originating_run_id, result.run_id)
        self.assertEqual(loaded_action.tool_call_id, "confirm-1")
        self.assertEqual(loaded_action.tool_name, CONFIRMATION_TOOL_NAME)
        self.assertEqual(loaded_action.arguments_hash, calculate_arguments_hash({"value": 95, "unit": "kg"}))
        self.assertEqual(loaded_action.expires_at, datetime(2026, 1, 1, 19, 19, 5, tzinfo=timezone.utc))

        self.assertIsNotNone(result.pending_action)
        self.assertEqual(result.pending_action.action_id, "action-1")
        self.assertEqual(result.pending_action.tool_name, CONFIRMATION_TOOL_NAME)
        payload = result.to_dict()
        self.assertEqual(
            set(payload["pendingAction"]),
            {"actionId", "toolName", "summary", "expiresAt"},
        )
        self.assertNotIn("arguments", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("argumentsHash", json.dumps(payload, ensure_ascii=False))

    def test_invalid_confirmation_arguments_return_tool_error_without_pending_action(self) -> None:
        handler_calls = {"confirmation": 0}
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call(
                            {"value": "95", "unit": "kg"},
                            id="invalid-confirm",
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="参数不合法，已改为提问。", finish_reason="stop"),
            ]
        )

        result = _run(
            provider,
            registry=_confirmation_registry(handler_calls),
            pending_store=pending_store,
            action_ids=["action-1"],
        )

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertIsNone(result.pending_action)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(handler_calls["confirmation"], 0)
        self.assertIsNone(pending_store.get("action-1"))
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant", "tool", "assistant"])
        self.assertEqual(_tool_json(result.messages[3])["error"]["code"], "invalid_arguments")

    def test_unknown_tool_returns_tool_error_without_pending_action(self) -> None:
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(
                            id="missing-1",
                            name="missing_tool",
                            arguments={"value": 1},
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="工具不存在。", finish_reason="stop"),
            ]
        )

        result = _run(
            provider,
            registry=_confirmation_registry({"confirmation": 0}),
            pending_store=pending_store,
            action_ids=["action-1"],
        )

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertIsNone(result.pending_action)
        self.assertEqual(result.tool_calls, 1)
        self.assertIsNone(pending_store.get("action-1"))
        self.assertEqual(_tool_json(result.messages[3])["error"]["code"], "unknown_tool")

    def test_read_only_before_confirmation_is_saved_then_pause_stops_remaining_tools(self) -> None:
        calls = {"read": 0, "confirmation": 0}
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _read_only_tool_call({"value": 1}, id="read-1"),
                        _confirmation_tool_call({"value": 95, "unit": "kg"}, id="confirm-1"),
                        _read_only_tool_call({"value": 2}, id="read-2"),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )

        result = _run(
            provider,
            registry=_mixed_registry(calls),
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-1"],
        )

        self.assertEqual(result.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(calls, {"read": 1, "confirmation": 0})
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant", "tool"])
        self.assertEqual(result.messages[3].tool_call_id, "read-1")
        self.assertEqual(len(provider.calls), 1)

        continuation = session_store.get(result.session_id).continuation
        self.assertEqual(continuation.assistant_message_index, 2)
        self.assertEqual(continuation.next_tool_call_index, 1)
        self.assertEqual(continuation.model_turns_used, 1)
        self.assertEqual(continuation.tool_calls_used, 1)
        action = pending_store.get("action-1")
        self.assertEqual(action.tool_call_index, 1)

    def test_confirmation_first_stops_later_read_only_tool(self) -> None:
        calls = {"read": 0, "confirmation": 0}
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call({"value": 95, "unit": "kg"}, id="confirm-1"),
                        _read_only_tool_call({"value": 2}, id="read-2"),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )

        result = _run(
            provider,
            registry=_mixed_registry(calls),
            action_ids=["action-1"],
        )

        self.assertEqual(result.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(calls, {"read": 0, "confirmation": 0})
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])

    def test_existing_waiting_session_returns_same_pending_action_without_model_call(self) -> None:
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        session_store.create(_waiting_session())
        pending_store.create(_pending_action())
        provider = ScriptedModelProvider([])

        result = _run(
            provider,
            registry=_confirmation_registry({"confirmation": 0}),
            session_store=session_store,
            pending_store=pending_store,
            user_text="用户又输入了一句",
        )

        self.assertEqual(result.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(result.model_turns, 0)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(result.pending_action.action_id, "action-1")
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])
        self.assertEqual([message.role for message in session_store.get("session-1").messages], ["system", "user", "assistant"])

    def test_waiting_session_missing_pending_action_fails_without_model_call(self) -> None:
        session_store = InMemorySessionStore()
        session_store.create(_waiting_session(pending_action_id="missing-action"))
        provider = ScriptedModelProvider([])

        result = _run(
            provider,
            registry=_confirmation_registry({"confirmation": 0}),
            session_store=session_store,
            pending_store=InMemoryPendingActionStore(),
        )

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_STATE_CONFLICT)
        self.assertEqual(len(provider.calls), 0)
        self.assertIsNone(result.pending_action)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])

    def test_confirmation_ttl_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            GenericAgentLoop(
                provider=ScriptedModelProvider([]),
                confirmation_ttl_seconds=0,
            )

    def test_session_version_conflict_after_pending_action_create_fails_closed(self) -> None:
        calls = {"confirmation": 0}
        session_store = ConflictOnWaitingSaveSessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _confirmation_tool_call({"value": 95, "unit": "kg"}, id="confirm-1"),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )

        result = _run(
            provider,
            registry=_confirmation_registry(calls),
            session_store=session_store,
            pending_store=pending_store,
            action_ids=["action-1"],
        )

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_VERSION_CONFLICT)
        self.assertEqual(calls["confirmation"], 0)
        self.assertIsNotNone(pending_store.get("action-1"))
        self.assertEqual(session_store.get(result.session_id).status, AgentSessionStatus.ACTIVE)
        self.assertIsNone(session_store.get(result.session_id).pending_action_id)


class ConflictOnWaitingSaveSessionStore(InMemorySessionStore):
    """在保存 WAITING_CONFIRMATION 时制造 CAS 冲突。

    该测试替身模拟 PendingAction 已创建、但 Session 指针保存失败的窗口，用来
    验证 GenericAgentLoop 会 fail closed，而不是继续执行或伪装成等待确认。
    """

    def save(self, session: AgentSession, expected_version: int) -> AgentSession:
        if session.status == AgentSessionStatus.WAITING_CONFIRMATION:
            raise SessionVersionConflictError("forced waiting save conflict")
        return super().save(session, expected_version)


class ControlledClock:
    """按顺序返回 monotonic 时间，便于断言暂停时剩余 active runtime。"""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self._last = values[-1] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


CONFIRMATION_TOOL_NAME = "record_weight_measurement"
READ_ONLY_TOOL_NAME = "lookup_profile_metric"


def _run(
    provider: ScriptedModelProvider,
    registry: ToolRegistry,
    *,
    session_store: InMemorySessionStore | None = None,
    pending_store: InMemoryPendingActionStore | None = None,
    action_ids: list[str] | None = None,
    limits: GenericLoopLimits | None = None,
    monotonic_provider=None,
    user_text: str = "记录体重",
) -> Any:
    """用固定时间和固定 action id 执行 GenericAgentLoop。"""

    ids = list(action_ids or ["action-default"])

    def next_action_id() -> str:
        return ids.pop(0)

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
    return loop.run(AgentRequest(user_text=user_text, session_id="session-1", locale="zh-CN"))


def _fixed_now() -> datetime:
    """固定为 +08:00，用于验证 Runtime 会写入 UTC continuation 时间。"""

    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=8)))


def _confirmation_registry(calls: dict[str, int]) -> ToolRegistry:
    """只包含 confirmation-required 工具的测试 registry。"""

    return ToolRegistry([_confirmation_tool(calls)])


def _mixed_registry(calls: dict[str, int]) -> ToolRegistry:
    """包含只读工具和 confirmation-required 工具的测试 registry。"""

    return ToolRegistry([_read_only_tool(calls), _confirmation_tool(calls)])


def _confirmation_tool(calls: dict[str, int]) -> ToolDefinition:
    """构造需要确认的测试工具；handler 被调用就说明暂停边界失效。"""

    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls["confirmation"] += 1
        return {"recorded": True}

    return ToolDefinition(
        name=CONFIRMATION_TOOL_NAME,
        description="Record a weight measurement after explicit confirmation",
        input_schema={"type": "object"},
        permission=ToolPermission.CONFIRMATION_REQUIRED,
        handler=handler,
        argument_validator=_validate_weight_arguments,
    )


def _read_only_tool(calls: dict[str, int]) -> ToolDefinition:
    """构造普通只读测试工具，用来验证暂停前的已执行工具会被保存。"""

    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls["read"] += 1
        return {"value": arguments["value"]}

    return ToolDefinition(
        name=READ_ONLY_TOOL_NAME,
        description="Read a profile metric",
        input_schema={"type": "object"},
        handler=handler,
    )


def _validate_weight_arguments(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    """只接受数值体重和 kg/lb 单位，确保非法参数不会进入 PendingAction。"""

    value = arguments.get("value")
    unit = str(arguments.get("unit") or "").strip()
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ToolArgumentError("value must be a number")
    if unit not in {"kg", "lb"}:
        raise ToolArgumentError("unit must be kg or lb")
    return {"value": value, "unit": unit}


def _confirmation_tool_call(arguments: Mapping[str, Any], id: str) -> ModelToolCall:
    """构造 confirmation-required ModelToolCall。"""

    return _tool_call(id=id, name=CONFIRMATION_TOOL_NAME, arguments=arguments)


def _read_only_tool_call(arguments: Mapping[str, Any], id: str) -> ModelToolCall:
    """构造 READ_ONLY ModelToolCall。"""

    return _tool_call(id=id, name=READ_ONLY_TOOL_NAME, arguments=arguments)


def _tool_call(id: str, name: str, arguments: Mapping[str, Any]) -> ModelToolCall:
    """构造带 deterministic raw_arguments 的 Tool Call。"""

    return ModelToolCall(
        id=id,
        name=name,
        raw_arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        arguments=arguments,
    )


def _tool_json(message: ModelMessage) -> dict[str, Any]:
    """解析 role=tool 消息内容。"""

    return json.loads(message.content or "")


def _waiting_session(pending_action_id: str = "action-1") -> AgentSession:
    """构造已等待确认的 Session。"""

    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.WAITING_CONFIRMATION,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="记录体重"),
            ModelMessage(
                role="assistant",
                tool_calls=(
                    _confirmation_tool_call({"value": 95, "unit": "kg"}, id="confirm-1"),
                ),
            ),
        ],
        pending_action_id=pending_action_id,
        continuation=_continuation(),
    )


def _continuation() -> AgentContinuation:
    """构造等待确认时保存的续点。"""

    started_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    return AgentContinuation(
        originating_run_id="run-previous",
        assistant_message_index=2,
        next_tool_call_index=0,
        model_turns_used=1,
        tool_calls_used=0,
        started_at=started_at,
        deadline_at=started_at + timedelta(seconds=60),
    )


def _pending_action() -> PendingAction:
    """构造与 _waiting_session 匹配的 PendingAction。"""

    created_at = datetime(2026, 1, 1, 19, 4, 5, tzinfo=timezone.utc)
    return PendingAction(
        action_id="action-1",
        session_id="session-1",
        originating_run_id="run-previous",
        tool_call_id="confirm-1",
        tool_name=CONFIRMATION_TOOL_NAME,
        arguments={"value": 95, "unit": "kg"},
        assistant_message_index=2,
        tool_call_index=0,
        summary='Tool "record_weight_measurement" requires user confirmation.',
        created_at=created_at,
        updated_at=created_at,
        expires_at=created_at + timedelta(minutes=15),
    )


if __name__ == "__main__":
    unittest.main()
