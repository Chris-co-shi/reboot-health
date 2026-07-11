import io
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.bootstrap import GenericRuntimeComponents
from agent.models import ModelMessage, ModelResponse, ProviderConfigurationError
from agent.runtime.confirmation_coordinator import ConfirmationCoordinator
from agent.runtime.pending_action import PendingAction
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionStoreError,
)
from agent.runtime.storage import JsonFilePendingActionStore, JsonFileSessionStore
from agent.runtime.generic_loop import GenericAgentLoop
from agent.tools.approved_executor import ApprovedActionExecutor
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry
from scripts import agent_chat
from tests.support.scripted_model_provider import ScriptedModelProvider


class AgentChatShellTest(unittest.TestCase):
    def test_startup_generates_current_session_id(self) -> None:
        components, _ = _components([])

        exit_code, stdout, _ = _run_shell(
            components,
            "/exit\n",
            session_id="generated-session",
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("Health Agent started. Session: generated-session", stdout)
        self.assertIn("Storage: memory", stdout)

    def test_two_user_inputs_use_same_session_and_second_call_has_history(self) -> None:
        components, provider = _components(
            [
                ModelResponse(content="请提供基础信息。", finish_reason="stop"),
                ModelResponse(content="继续补充年龄和身高。", finish_reason="stop"),
            ]
        )

        exit_code, stdout, _ = _run_shell(
            components,
            "帮我设计增肌计划\n有训练过，每周五天\n/exit\n",
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(
            [message.role for message in provider.calls[0]["messages"]],
            ["system", "user"],
        )
        second_messages = provider.calls[1]["messages"]
        self.assertEqual(
            [message.role for message in second_messages],
            ["system", "user", "assistant", "user"],
        )
        self.assertEqual(second_messages[1].content, "帮我设计增肌计划")
        self.assertEqual(second_messages[2].content, "请提供基础信息。")
        self.assertEqual(second_messages[3].content, "有训练过，每周五天")
        self.assertIn("Run summary: status=completed", stdout)

    def test_new_switches_session_and_isolates_history(self) -> None:
        components, provider = _components(
            [
                ModelResponse(content="第一轮回答", finish_reason="stop"),
                ModelResponse(content="新会话回答", finish_reason="stop"),
            ]
        )

        exit_code, stdout, _ = _run_shell(
            components,
            "第一轮\n/new\n第二轮\n/exit\n",
            new_ids=["session-2"],
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("已切换到新 Session: session-2", stdout)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(
            [message.role for message in provider.calls[1]["messages"]],
            ["system", "user"],
        )
        self.assertEqual(provider.calls[1]["messages"][1].content, "第二轮")
        self.assertNotIn("第一轮", [m.content for m in provider.calls[1]["messages"]])

    def test_resume_existing_session_restores_history(self) -> None:
        components, provider = _components(
            [
                ModelResponse(content="先问基础信息。", finish_reason="stop"),
                ModelResponse(content="回到旧话题继续。", finish_reason="stop"),
            ]
        )

        exit_code, stdout, _ = _run_shell(
            components,
            "增肌计划\n/new\n/resume session-1\n继续\n/exit\n",
            new_ids=["session-2"],
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("已切换到 Session: session-1", stdout)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(
            [message.role for message in provider.calls[1]["messages"]],
            ["system", "user", "assistant", "user"],
        )
        self.assertEqual(provider.calls[1]["messages"][1].content, "增肌计划")
        self.assertEqual(provider.calls[1]["messages"][3].content, "继续")

    def test_resume_missing_session_does_not_call_model(self) -> None:
        components, provider = _components([])

        exit_code, stdout, _ = _run_shell(
            components,
            "/resume missing\n/exit\n",
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("Session 不存在", stdout)
        self.assertEqual(provider.calls, [])

    def test_unknown_command_and_empty_input_do_not_call_model(self) -> None:
        components, provider = _components([])

        exit_code, stdout, _ = _run_shell(
            components,
            "\n/unknown\n   \n/exit\n",
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("未知命令：/unknown", stdout)
        self.assertEqual(provider.calls, [])

    def test_new_store_error_does_not_switch_session(self) -> None:
        components, provider = _components(
            [],
            session_store=_FailingGetSessionStore(),
        )

        exit_code, stdout, stderr = _run_shell(
            components,
            "/new\n/exit\n",
            new_ids=["session-2"],
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(provider.calls, [])
        self.assertNotIn("session-2", stdout)
        self.assertIn("Session Store 错误", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_status_for_uncreated_session_is_safe_summary(self) -> None:
        components, _ = _components([])

        exit_code, stdout, _ = _run_shell(
            components,
            "/status\n/exit\n",
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("Status: not_created", stdout)
        self.assertIn("Messages: 0", stdout)
        self.assertIn("尚未首次持久化", stdout)
        self.assertNotIn("system", stdout)

    def test_eof_and_keyboard_interrupt_exit_safely(self) -> None:
        components, _ = _components([])

        eof_code, eof_stdout, _ = _run_shell(components, "")
        interrupt_code, interrupt_stdout, _ = _run_shell(
            components,
            _InterruptingInput(),
        )

        self.assertEqual(eof_code, 0)
        self.assertEqual(interrupt_code, 0)
        self.assertIn("已退出。", eof_stdout)
        self.assertIn("已退出。", interrupt_stdout)

    def test_json_recreated_components_restore_session_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_components, first_provider = _components(
                [ModelResponse(content="第一轮回答。", finish_reason="stop")],
                storage_directory=Path(directory),
            )
            first_code, _, _ = _run_shell(
                first_components,
                "第一轮问题\n/exit\n",
                storage_mode="json",
                session_id="persisted-session",
            )

            second_components, second_provider = _components(
                [ModelResponse(content="第二轮回答。", finish_reason="stop")],
                storage_directory=Path(directory),
            )
            second_code, _, _ = _run_shell(
                second_components,
                "第二轮问题\n/exit\n",
                storage_mode="json",
                session_id="persisted-session",
            )

        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertEqual(len(first_provider.calls), 1)
        self.assertEqual(len(second_provider.calls), 1)
        self.assertEqual(
            [message.role for message in second_provider.calls[0]["messages"]],
            ["system", "user", "assistant", "user"],
        )
        self.assertEqual(
            second_provider.calls[0]["messages"][1].content,
            "第一轮问题",
        )

    def test_running_session_is_not_bypassed(self) -> None:
        store = InMemorySessionStore()
        heartbeat = _fixed_utc_now()
        store.create(
            AgentSession(
                session_id="session-1",
                status=AgentSessionStatus.RUNNING,
                active_run_id="run-active",
                run_fence_generation=1,
                active_run_last_heartbeat_at=heartbeat,
                active_run_lease_expires_at=heartbeat + timedelta(minutes=5),
            )
        )
        components, provider = _components([], session_store=store)

        exit_code, stdout, _ = _run_shell(
            components,
            "继续\n/exit\n",
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(provider.calls, [])
        self.assertIn("SESSION_ALREADY_RUNNING", stdout)

    def test_waiting_confirmation_does_not_treat_text_as_approval(self) -> None:
        session_store = InMemorySessionStore()
        pending_store = InMemoryPendingActionStore()
        session_store.create(
            AgentSession(
                session_id="session-1",
                status=AgentSessionStatus.WAITING_CONFIRMATION,
                pending_action_id="action-1",
            )
        )
        pending_store.create(
            PendingAction(
                action_id="action-1",
                session_id="session-1",
                originating_run_id="run-1",
                tool_call_id="call-1",
                tool_name="future_write_tool",
                arguments={"value": 1},
                assistant_message_index=0,
                tool_call_index=0,
                summary="需要确认。",
                expires_at=_fixed_utc_now() + timedelta(minutes=5),
                created_at=_fixed_utc_now(),
                updated_at=_fixed_utc_now(),
            )
        )
        components, provider = _components(
            [],
            session_store=session_store,
            pending_store=pending_store,
        )

        exit_code, stdout, _ = _run_shell(
            components,
            "approve\n/exit\n",
        )

        stored = session_store.get("session-1")
        self.assertEqual(exit_code, 0)
        self.assertEqual(provider.calls, [])
        self.assertIn("等待确认", stdout)
        self.assertEqual(stored.status, AgentSessionStatus.WAITING_CONFIRMATION)
        self.assertEqual(len(stored.messages), 0)

    def test_failed_session_is_not_silently_reset(self) -> None:
        session_store = InMemorySessionStore()
        session_store.create(
            AgentSession(
                session_id="session-1",
                status=AgentSessionStatus.FAILED,
                messages=[ModelMessage(role="user", content="旧消息")],
            )
        )
        components, provider = _components([], session_store=session_store)

        exit_code, stdout, _ = _run_shell(
            components,
            "继续\n/exit\n",
        )

        stored = session_store.get("session-1")
        self.assertEqual(exit_code, 0)
        self.assertEqual(provider.calls, [])
        self.assertIn("SESSION_STATE_CONFLICT", stdout)
        self.assertEqual(stored.status, AgentSessionStatus.FAILED)
        self.assertEqual(len(stored.messages), 1)


class AgentChatMainTest(unittest.TestCase):
    def test_json_mode_requires_storage_directory(self) -> None:
        stderr = io.StringIO()

        exit_code = agent_chat.main(["--storage", "json"], stderr=stderr)

        self.assertEqual(exit_code, agent_chat.EXIT_CONFIGURATION_ERROR)
        self.assertIn("--storage-directory", stderr.getvalue())

    def test_memory_mode_does_not_write_storage_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            components, _ = _components([])
            stdout = io.StringIO()

            exit_code = agent_chat.main(
                ["--storage", "memory", "--storage-directory", directory],
                runtime_components_factory=lambda **_: components,
                stdin=io.StringIO("/exit\n"),
                stdout=stdout,
                session_id_factory=lambda: "session-main",
            )

            children = list(Path(directory).iterdir())

        self.assertEqual(exit_code, 0)
        self.assertEqual(children, [])
        self.assertIn("Session: session-main", stdout.getvalue())

    def test_configuration_error_redacts_secret(self) -> None:
        stderr = io.StringIO()

        exit_code = agent_chat.main(
            [],
            runtime_components_factory=lambda **_: _raise_config_error(),
            stdin=io.StringIO("/exit\n"),
            stderr=stderr,
            session_id_factory=lambda: "session-main",
        )

        self.assertEqual(exit_code, agent_chat.EXIT_CONFIGURATION_ERROR)
        self.assertNotIn("sk-test-secret", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


def _run_shell(
    components: GenericRuntimeComponents,
    input_value,
    *,
    storage_mode: str = "memory",
    session_id: str = "session-1",
    new_ids: list[str] | None = None,
) -> tuple[int, str, str]:
    stdin = input_value if hasattr(input_value, "readline") else io.StringIO(input_value)
    stdout = io.StringIO()
    stderr = io.StringIO()
    shell = agent_chat.AgentChatShell(
        components=components,
        config=agent_chat.AgentChatConfig(
            storage_mode=storage_mode,
            storage_directory=None,
            session_id=session_id,
        ),
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        session_id_factory=_id_factory(new_ids or []),
    )

    return shell.run(), stdout.getvalue(), stderr.getvalue()


def _components(
    responses: list[ModelResponse],
    *,
    session_store=None,
    pending_store=None,
    storage_directory: Path | None = None,
) -> tuple[GenericRuntimeComponents, ScriptedModelProvider]:
    provider = ScriptedModelProvider(responses)
    if storage_directory is not None:
        session_store = JsonFileSessionStore(storage_directory, now_provider=_fixed_utc_now)
        pending_store = JsonFilePendingActionStore(
            storage_directory,
            now_provider=_fixed_utc_now,
        )
    session_store = session_store or InMemorySessionStore()
    pending_store = pending_store or InMemoryPendingActionStore()
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    loop = GenericAgentLoop(
        provider=provider,
        session_store=session_store,
        pending_action_store=pending_store,
        tool_registry=registry,
        tool_executor=executor,
        now_provider=_fixed_provider_now,
    )
    approved_executor = ApprovedActionExecutor(
        pending_action_store=pending_store,
        tool_registry=registry,
    )
    coordinator = ConfirmationCoordinator(
        session_store=session_store,
        pending_action_store=pending_store,
        tool_registry=registry,
        approved_action_executor=approved_executor,
    )
    return (
        GenericRuntimeComponents(
            loop=loop,
            confirmation_coordinator=coordinator,
            session_store=session_store,
            pending_action_store=pending_store,
            tool_registry=registry,
            tool_executor=executor,
            approved_action_executor=approved_executor,
        ),
        provider,
    )


def _id_factory(values: list[str]):
    remaining = list(values)

    def make_id() -> str:
        return remaining.pop(0) if remaining else "generated-session"

    return make_id


def _fixed_provider_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _fixed_utc_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _raise_config_error():
    raise ProviderConfigurationError("Missing LLM_API_KEY sk-test-secret")


class _InterruptingInput:
    def readline(self) -> str:
        raise KeyboardInterrupt


class _FailingGetSessionStore(InMemorySessionStore):
    def get(self, session_id: str):
        raise SessionStoreError("Session store read failed sk-test-secret")


if __name__ == "__main__":
    unittest.main()
