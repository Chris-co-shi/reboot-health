import json
import unittest
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from agent.models import (
    ModelMessage,
    ModelOptions,
    ModelProvider,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
)
from agent.runtime.execution_checkpoint import RunExecutionCheckpointPhase
from agent.runtime.generic_loop import (
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_WAITING_CONFIRMATION,
    AgentRequest,
    GenericAgentLoop,
    GenericLoopLimits,
)
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.runtime.session import AgentSessionStatus, InMemorySessionStore
from agent.tools.contract import ToolDefinition, ToolPermission
from agent.tools.registry import ToolRegistry


READ_TOOL_NAME = "read_metric"
CONFIRM_TOOL_NAME = "record_metric"


class ExecutionCheckpointLoopTest(unittest.TestCase):
    """验证 checkpoint 写入围绕真实模型/工具调用窗口发生。"""

    def test_model_in_flight_checkpoint_is_persisted_before_provider_call(self) -> None:
        session_store = InMemorySessionStore()
        observed_phases: list[RunExecutionCheckpointPhase] = []

        provider = CallbackProvider(
            [
                ModelResponse(content="完成", finish_reason="stop"),
            ],
            on_call=lambda: observed_phases.append(
                session_store.get("session-1").execution_checkpoint.checkpoint_phase
            ),
        )
        loop = _loop(provider, session_store=session_store)

        result = loop.run(AgentRequest("直接完成", session_id="session-1"))
        stored = session_store.get("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(observed_phases, [RunExecutionCheckpointPhase.MODEL_CALL_IN_FLIGHT])
        self.assertEqual(stored.status, AgentSessionStatus.COMPLETED)
        self.assertIsNone(stored.execution_checkpoint)

    def test_tool_in_flight_checkpoint_is_persisted_before_handler_call(self) -> None:
        session_store = InMemorySessionStore()
        observed_phases: list[RunExecutionCheckpointPhase] = []

        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            observed_phases.append(
                session_store.get("session-1").execution_checkpoint.checkpoint_phase
            )
            return {"value": arguments["value"]}

        provider = CallbackProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(
                            id="read-1",
                            name=READ_TOOL_NAME,
                            arguments={"value": 7},
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="读取完成", finish_reason="stop"),
            ]
        )
        loop = _loop(
            provider,
            session_store=session_store,
            registry=ToolRegistry([_read_tool(handler)]),
        )

        result = loop.run(AgentRequest("读取指标", session_id="session-1"))
        stored = session_store.get("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(observed_phases, [RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT])
        self.assertIsNone(stored.execution_checkpoint)

    def test_waiting_confirmation_clears_execution_checkpoint(self) -> None:
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        provider = CallbackProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(
                            id="confirm-1",
                            name=CONFIRM_TOOL_NAME,
                            arguments={"value": 7},
                        ),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )
        loop = _loop(
            provider,
            session_store=session_store,
            pending_store=pending_store,
            registry=ToolRegistry([_confirmation_tool()]),
        )

        result = loop.run(AgentRequest("记录指标", session_id="session-1"))
        stored = session_store.get("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(stored.status, AgentSessionStatus.WAITING_CONFIRMATION)
        self.assertIsNone(stored.execution_checkpoint)
        self.assertIsNotNone(pending_store.get(result.pending_action.action_id))


class CallbackProvider(ModelProvider):
    provider_name = "callback-provider"

    def __init__(
        self,
        responses: Sequence[ModelResponse],
        *,
        on_call=None,
    ) -> None:
        self.responses = list(responses)
        self.on_call = on_call
        self.calls = 0

    def complete_turn(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition] = (),
        options: ModelOptions | None = None,
    ) -> ModelResponse:
        self.calls += 1
        if self.on_call is not None:
            self.on_call()
        return self.responses.pop(0)


def _loop(
    provider: ModelProvider,
    *,
    session_store: InMemorySessionStore,
    pending_store: InMemoryPendingActionStore | None = None,
    registry: ToolRegistry | None = None,
) -> GenericAgentLoop:
    return GenericAgentLoop(
        provider=provider,
        limits=GenericLoopLimits(timeout_seconds=60),
        session_store=session_store,
        pending_action_store=pending_store or InMemoryPendingActionStore(),
        tool_registry=registry or ToolRegistry(),
        now_provider=_fixed_now,
        monotonic_provider=lambda: 0.0,
        action_id_factory=lambda: "action-1",
    )


def _read_tool(handler) -> ToolDefinition:
    return ToolDefinition(
        name=READ_TOOL_NAME,
        description="Read metric",
        input_schema={"type": "object"},
        handler=handler,
    )


def _confirmation_tool() -> ToolDefinition:
    return ToolDefinition(
        name=CONFIRM_TOOL_NAME,
        description="Record metric after confirmation",
        input_schema={"type": "object"},
        permission=ToolPermission.CONFIRMATION_REQUIRED,
        handler=lambda arguments: {"recorded": True},
    )


def _tool_call(
    *,
    id: str,
    name: str,
    arguments: Mapping[str, Any],
) -> ModelToolCall:
    return ModelToolCall(
        id=id,
        name=name,
        raw_arguments=json.dumps(arguments, sort_keys=True),
        arguments=arguments,
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
