import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from agent.models import ModelMessage, ModelResponse, ModelToolCall
from agent.runtime.confirmation import ConfirmationDecision, ConfirmationDecisionType
from agent.runtime.confirmation_coordinator import (
    TOOL_REJECTED_BY_USER,
    ConfirmationCoordinator,
)
from agent.runtime.generic_loop import (
    ERROR_SESSION_ALREADY_RUNNING,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_FAILED,
    GENERIC_STATUS_WAITING_CONFIRMATION,
    AgentRequest,
    GenericAgentLoop,
)
from agent.runtime.pending_action import PendingActionStatus
from agent.runtime.session import AgentSession, AgentSessionStatus
from agent.runtime.storage import JsonFilePendingActionStore, JsonFileSessionStore
from agent.tools.contract import ToolDefinition, ToolPermission
from agent.tools.registry import ToolRegistry

from tests.support.scripted_model_provider import ScriptedModelProvider


CONFIRMATION_TOOL_NAME = "record_weight_measurement"


class JsonStoreRestartTest(unittest.TestCase):
    """JSON Store 必须支持进程重启后的 Runtime 状态恢复。

    这里的“重启”用重新创建 Store/Loop 实例表达：旧对象不再被使用，新对象只从
    同一个 data_dir 读取 JSON 文件。这样可以直接证明持久化内容足够恢复 Agent
    Loop 和 ConfirmationCoordinator 的协作状态。
    """

    def test_active_session_survives_store_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            first_store.create(
                AgentSession(
                    session_id="session-1",
                    status=AgentSessionStatus.ACTIVE,
                    messages=[
                        ModelMessage(role="user", content="记录一下体重"),
                        ModelMessage(role="assistant", content="可以记录。"),
                    ],
                    context_summary="已有一次对话",
                )
            )

            # 重建 Store 实例后只能依赖磁盘 JSON；这里不复用 first_store 的内存对象。
            second_store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            loaded = second_store.get("session-1")

            self.assertEqual(loaded.status, AgentSessionStatus.ACTIVE)
            self.assertEqual(loaded.context_summary, "已有一次对话")
            self.assertEqual([message.role for message in loaded.messages], ["user", "assistant"])
            loaded.messages.append(ModelMessage(role="assistant", content="本地修改"))
            self.assertEqual(len(second_store.get("session-1").messages), 2)

    def test_waiting_confirmation_survives_store_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = {"confirmation": 0}
            session_store, pending_store = _stores(directory)
            provider = ScriptedModelProvider(
                [
                    ModelResponse(
                        tool_calls=(
                            _confirmation_tool_call({"value": 95, "unit": "kg"}, "call-1"),
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            )
            loop, _ = _loop(
                provider,
                calls,
                session_store=session_store,
                pending_store=pending_store,
                action_ids=["action-1"],
            )

            paused = loop.run(AgentRequest("记录体重", session_id="session-1"))
            reloaded_sessions, reloaded_actions = _stores(directory)
            reloaded_session = reloaded_sessions.get(paused.session_id)
            reloaded_action = reloaded_actions.get(paused.pending_action.action_id)

            self.assertEqual(paused.status, GENERIC_STATUS_WAITING_CONFIRMATION)
            self.assertEqual(reloaded_session.status, AgentSessionStatus.WAITING_CONFIRMATION)
            self.assertEqual(reloaded_session.pending_action_id, "action-1")
            self.assertEqual(reloaded_session.continuation.originating_run_id, paused.run_id)
            self.assertEqual(reloaded_action.status, PendingActionStatus.PENDING)
            self.assertEqual(reloaded_action.session_id, "session-1")
            self.assertEqual(reloaded_action.tool_call_id, "call-1")
            self.assertEqual(calls["confirmation"], 0)
            self.assertEqual(len(provider.calls), 1)

    def test_approved_action_resumes_after_restart_without_reexecuting_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = {"confirmation": 0}
            session_store, pending_store = _stores(directory)
            provider = ScriptedModelProvider(
                [
                    ModelResponse(
                        tool_calls=(
                            _confirmation_tool_call({"value": 95, "unit": "kg"}, "call-1"),
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
                action_ids=["action-1"],
            )
            paused = loop.run(AgentRequest("记录体重", session_id="session-1"))

            _coordinator(session_store, pending_store, registry).resolve(
                ConfirmationDecision(
                    session_id=paused.session_id,
                    action_id="action-1",
                    decision=ConfirmationDecisionType.APPROVE,
                )
            )

            # 新 Loop 使用新的 Store 实例和新的 Provider，只从磁盘恢复确认后的状态。
            restarted_sessions, restarted_actions = _stores(directory)
            resumed_provider = ScriptedModelProvider(
                [ModelResponse(content="已记录。", finish_reason="stop")]
            )
            resumed_loop, _ = _loop(
                resumed_provider,
                calls,
                session_store=restarted_sessions,
                pending_store=restarted_actions,
            )
            resumed = resumed_loop.resume(paused.session_id)

            self.assertEqual(resumed.status, GENERIC_STATUS_COMPLETED)
            self.assertEqual(resumed.model_turns, 2)
            self.assertEqual(resumed.tool_calls, 1)
            self.assertEqual(calls["confirmation"], 1)
            self.assertEqual(
                [message.role for message in resumed_provider.calls[0]["messages"]],
                ["system", "user", "assistant", "tool"],
            )
            self.assertEqual(
                [message.role for message in resumed_provider.calls[0]["messages"]].count("user"),
                1,
            )
            self.assertEqual(
                restarted_actions.get("action-1").status,
                PendingActionStatus.EXECUTED,
            )
            self.assertEqual(
                restarted_sessions.get("session-1").status,
                AgentSessionStatus.COMPLETED,
            )

    def test_rejected_action_resumes_after_restart_without_executing_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = {"confirmation": 0}
            session_store, pending_store = _stores(directory)
            provider = ScriptedModelProvider(
                [
                    ModelResponse(
                        tool_calls=(
                            _confirmation_tool_call({"value": 95, "unit": "kg"}, "call-1"),
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
                action_ids=["action-1"],
            )
            paused = loop.run(AgentRequest("记录体重", session_id="session-1"))

            _coordinator(session_store, pending_store, registry).resolve(
                ConfirmationDecision(
                    session_id=paused.session_id,
                    action_id="action-1",
                    decision=ConfirmationDecisionType.REJECT,
                    reason="用户取消",
                )
            )

            restarted_sessions, restarted_actions = _stores(directory)
            resumed_provider = ScriptedModelProvider(
                [ModelResponse(content="已取消。", finish_reason="stop")]
            )
            resumed_loop, _ = _loop(
                resumed_provider,
                calls,
                session_store=restarted_sessions,
                pending_store=restarted_actions,
            )
            resumed = resumed_loop.resume(paused.session_id)
            tool_payload = json.loads(resumed_provider.calls[0]["messages"][-1].content)

            self.assertEqual(resumed.status, GENERIC_STATUS_COMPLETED)
            self.assertEqual(resumed.tool_calls, 1)
            self.assertEqual(calls["confirmation"], 0)
            self.assertEqual(tool_payload["error"]["code"], TOOL_REJECTED_BY_USER)
            self.assertEqual(
                restarted_actions.get("action-1").status,
                PendingActionStatus.REJECTED,
            )

    def test_running_status_survives_restart_and_blocks_new_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_store, pending_store = _stores(directory)
            session_store.create(
                AgentSession(
                    session_id="session-1",
                    status=AgentSessionStatus.RUNNING,
                    active_run_id="run-in-flight",
                )
            )

            restarted_sessions, restarted_actions = _stores(directory)
            provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
            loop, _ = _loop(
                provider,
                {"confirmation": 0},
                session_store=restarted_sessions,
                pending_store=restarted_actions,
            )

            run_result = loop.run(AgentRequest("新任务", session_id="session-1"))
            resume_result = loop.resume("session-1")

            self.assertEqual(run_result.status, GENERIC_STATUS_FAILED)
            self.assertEqual(run_result.error.code, ERROR_SESSION_ALREADY_RUNNING)
            self.assertEqual(resume_result.status, GENERIC_STATUS_FAILED)
            self.assertEqual(resume_result.error.code, ERROR_SESSION_ALREADY_RUNNING)
            self.assertEqual(len(provider.calls), 0)


def _stores(
    directory: str | Path,
) -> tuple[JsonFileSessionStore, JsonFilePendingActionStore]:
    """创建指向同一个目录的 JSON Store 对，模拟同一 Runtime 状态仓库。"""

    return (
        JsonFileSessionStore(directory, now_provider=_fixed_now),
        JsonFilePendingActionStore(directory, now_provider=_fixed_now),
    )


def _loop(
    provider: ScriptedModelProvider,
    calls: dict[str, int],
    *,
    session_store: JsonFileSessionStore,
    pending_store: JsonFilePendingActionStore,
    action_ids: list[str] | None = None,
) -> tuple[GenericAgentLoop, ToolRegistry]:
    """创建测试 Loop，并把动作 ID 固定下来方便断言磁盘文件内容。"""

    remaining_action_ids = list(action_ids or ["action-default"])

    def next_action_id() -> str:
        return remaining_action_ids.pop(0)

    registry = _registry(calls)
    return (
        GenericAgentLoop(
            provider=provider,
            session_store=session_store,
            pending_action_store=pending_store,
            now_provider=_fixed_now,
            tool_registry=registry,
            action_id_factory=next_action_id,
        ),
        registry,
    )


def _coordinator(
    session_store: JsonFileSessionStore,
    pending_store: JsonFilePendingActionStore,
    registry: ToolRegistry,
) -> ConfirmationCoordinator:
    """创建与 Loop 共用 JSON Store 的确认协调器。"""

    return ConfirmationCoordinator(
        session_store=session_store,
        pending_action_store=pending_store,
        tool_registry=registry,
        now_provider=_fixed_now,
    )


def _registry(calls: dict[str, int]) -> ToolRegistry:
    """测试只需要一个确认型工具，便于观察是否发生重复执行。"""

    return ToolRegistry([_confirmation_tool(calls)])


def _confirmation_tool(calls: dict[str, int]) -> ToolDefinition:
    """确认型测试工具：只有 APPROVE 决策会触发 handler。"""

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


def _confirmation_tool_call(arguments: Mapping[str, Any], id: str) -> ModelToolCall:
    """构造模型返回的 confirmation tool call。"""

    return ModelToolCall(
        id=id,
        name=CONFIRMATION_TOOL_NAME,
        raw_arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        arguments=arguments,
    )


def _fixed_now() -> datetime:
    """测试使用固定 UTC 时间，避免 JSON round-trip 受本地时区影响。"""

    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
