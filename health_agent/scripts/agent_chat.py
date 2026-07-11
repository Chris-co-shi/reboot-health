"""Health Agent 交互式本地 Session CLI。

Phase 2C 只把现有 GenericAgentLoop、SessionStore 和 JSON Store 组装成连续
对话入口；本文件不实现健康领域持久化、确认审批命令或长期 Memory。
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.bootstrap import (
    GenericRuntimeComponents,
    create_generic_runtime_components_from_env,
)
from agent.models import ProviderConfigurationError
from agent.runtime.generic_loop import (
    AgentRequest,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_WAITING_CONFIRMATION,
)
from agent.runtime.pending_action_store import PendingActionStoreError
from agent.runtime.result import AgentRunResult
from agent.runtime.session import AgentSession, SessionStoreError
from agent.runtime.storage.errors import JsonStoreError

EXIT_SUCCESS = 0
EXIT_CONFIGURATION_ERROR = 2
JSON_PLAINTEXT_NOTICE = (
    "注意：JSON Session 数据会以本地明文保存，仅适合受控本地环境。"
)


@dataclass(frozen=True)
class AgentChatConfig:
    """交互式 CLI 的显式启动配置。"""

    storage_mode: str
    storage_directory: Path | None
    session_id: str


class AgentChatShell:
    """单进程交互式 Session Shell。

    Shell 自身只维护当前 session_id 和命令解析；模型调用、消息追加、lease、
    fencing、checkpoint 与 JSON 持久化仍全部交给现有 Runtime Components。
    """

    def __init__(
        self,
        *,
        components: GenericRuntimeComponents,
        config: AgentChatConfig,
        stdin: TextIO,
        stdout: TextIO,
        stderr: TextIO,
        session_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.components = components
        self.config = config
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.session_id_factory = session_id_factory or _new_session_id
        self.current_session_id = config.session_id

    def run(self) -> int:
        """启动交互式输入循环，EOF/Ctrl-C 均按正常退出处理。"""

        self._print_startup()
        while True:
            try:
                line = self._read_user_line()
            except (EOFError, KeyboardInterrupt):
                self._print("已退出。")
                return EXIT_SUCCESS

            text = line.strip()
            if not text:
                continue
            if text.startswith("/"):
                should_continue = self._handle_command(text)
                if not should_continue:
                    return EXIT_SUCCESS
                continue
            self._run_user_text(text)

    def _print_startup(self) -> None:
        self._print(f"Health Agent started. Session: {self.current_session_id}")
        self._print(f"Storage: {self.config.storage_mode}")
        if self.config.storage_mode == "json":
            self._print(JSON_PLAINTEXT_NOTICE)
        self._print("输入 /help 查看命令，/exit 退出。")

    def _read_user_line(self) -> str:
        self._print("You: ", end="", flush=True)
        line = self.stdin.readline()
        if line == "":
            raise EOFError
        return line.rstrip("\n")

    def _handle_command(self, command_line: str) -> bool:
        command, _, rest = command_line.partition(" ")
        if command == "/help":
            self._print_help()
            return True
        if command == "/new":
            self._new_session()
            return True
        if command == "/status":
            self._print_status()
            return True
        if command == "/resume":
            self._resume_session(rest.strip())
            return True
        if command == "/exit":
            self._print("已退出。")
            return False

        self._print(f"未知命令：{command}")
        self._print_help()
        return True

    def _print_help(self) -> None:
        self._print("可用命令：")
        self._print("  /help                 显示命令和当前存储模式")
        self._print("  /new                  创建并切换到新的本地 Session")
        self._print("  /status               显示当前 Session 安全摘要")
        self._print("  /resume <session-id>  切换到已存在的 Session")
        self._print("  /exit                 正常退出")
        self._print(f"当前 storage：{self.config.storage_mode}")
        if self.config.storage_mode == "json":
            self._print(JSON_PLAINTEXT_NOTICE)

    def _new_session(self) -> None:
        session_id = self._generate_unused_session_id()
        if session_id is None:
            self._print_store_error("Session Store 错误，未切换到新 Session。")
            return
        self.current_session_id = session_id
        self._print(f"已切换到新 Session: {self.current_session_id}")

    def _generate_unused_session_id(self) -> str | None:
        for _ in range(10):
            candidate = self.session_id_factory()
            try:
                if self.components.session_store.get(candidate) is None:
                    return candidate
            except SessionStoreError:
                return None
        return self.session_id_factory()

    def _print_status(self) -> None:
        try:
            session = self.components.session_store.get(self.current_session_id)
        except SessionStoreError:
            self._print_store_error("Session 状态读取失败。")
            return
        self._print_session_summary(session)

    def _resume_session(self, session_id: str) -> None:
        if not session_id:
            self._print("错误：/resume 需要提供 session-id。")
            self._print_help()
            return
        try:
            session = self.components.session_store.get(session_id)
        except SessionStoreError:
            self._print_store_error("Session 读取失败。")
            return
        if session is None:
            self._print("错误：Session 不存在，未切换，也未调用模型。")
            return
        self.current_session_id = session.session_id
        self._print(f"已切换到 Session: {self.current_session_id}")
        self._print_session_summary(session)

    def _run_user_text(self, user_text: str) -> None:
        try:
            result = self.components.loop.run(
                AgentRequest(
                    user_text=user_text,
                    session_id=self.current_session_id,
                )
            )
        except SessionStoreError:
            self._print_store_error("Session Store 错误，未完成本轮运行。")
            return
        except PendingActionStoreError:
            self._print_store_error("PendingAction Store 错误，未完成本轮运行。")
            return
        except ValueError as exc:
            self._print(f"输入错误：{_redact_text(str(exc))}")
            return

        self._print_run_result(result)

    def _print_run_result(self, result: AgentRunResult) -> None:
        if result.status == GENERIC_STATUS_COMPLETED:
            self._print(f"Agent: {_public_answer(result.final_text) or ''}")
        elif result.status == GENERIC_STATUS_WAITING_CONFIRMATION:
            self._print(
                "Agent: 当前 Session 正在等待确认；Phase 2C 不把普通文本当作批准。"
            )
            if result.pending_action is not None:
                self._print(
                    f"Pending action: tool={result.pending_action.tool_name}"
                )
        else:
            error = result.error
            if error is None:
                self._print(f"Agent error: status={result.status}")
            else:
                self._print(
                    "Agent error: "
                    f"{error.code}: {_redact_text(error.message)}"
                )

        self._print(
            "Run summary: "
            f"status={result.status} "
            f"modelTurns={result.model_turns} "
            f"toolCalls={result.tool_calls} "
            f"session={result.session_id}"
        )

    def _print_session_summary(self, session: AgentSession | None) -> None:
        if session is None:
            status = "not_created"
            message_count = 0
            persisted = "no"
        else:
            status = session.status.value
            message_count = len(session.messages)
            persisted = "yes"
        self._print(f"Session: {self.current_session_id}")
        self._print(f"Status: {status}")
        self._print(f"Messages: {message_count}")
        self._print(f"Storage: {self.config.storage_mode}")
        self._print(f"Persisted: {persisted}")
        if persisted == "no":
            self._print("提示：当前 Session 尚未首次持久化。")
        if self.config.storage_mode == "json":
            self._print(JSON_PLAINTEXT_NOTICE)

    def _print_store_error(self, message: str) -> None:
        self._print(f"错误：{message}", file=self.stderr)

    def _print(
        self,
        text: str,
        *,
        file: TextIO | None = None,
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        print(text, file=file or self.stdout, end=end, flush=flush)


def main(
    argv: Sequence[str] | None = None,
    *,
    runtime_components_factory: Callable[..., GenericRuntimeComponents] = (
        create_generic_runtime_components_from_env
    ),
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    session_id_factory: Callable[[], str] | None = None,
) -> int:
    """解析参数、创建一次 Runtime Components，并进入交互循环。"""

    out = stdout or sys.stdout
    err = stderr or sys.stderr
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    storage_directory = Path(args.storage_directory) if args.storage_directory else None
    if args.storage == "json" and storage_directory is None:
        print("error: --storage-directory is required when --storage json", file=err)
        return EXIT_CONFIGURATION_ERROR

    make_session_id = session_id_factory or _new_session_id
    session_id = _normalize_session_id(args.session_id) or make_session_id()
    config = AgentChatConfig(
        storage_mode=args.storage,
        storage_directory=storage_directory,
        session_id=session_id,
    )

    try:
        components = runtime_components_factory(
            storage_mode=config.storage_mode,
            storage_directory=config.storage_directory,
        )
    except ProviderConfigurationError as exc:
        print(f"configuration error: {_redact_text(str(exc))}", file=err)
        return EXIT_CONFIGURATION_ERROR
    except (JsonStoreError, SessionStoreError, PendingActionStoreError, ValueError) as exc:
        print(f"configuration error: {_redact_text(str(exc))}", file=err)
        return EXIT_CONFIGURATION_ERROR

    shell = AgentChatShell(
        components=components,
        config=config,
        stdin=stdin or sys.stdin,
        stdout=out,
        stderr=err,
        session_id_factory=make_session_id,
    )
    return shell.run()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Health Agent interactive session shell."
    )
    parser.add_argument(
        "--storage",
        choices=("memory", "json"),
        default="memory",
        help="Session storage mode. Defaults to memory.",
    )
    parser.add_argument(
        "--storage-directory",
        help="Directory for explicit json storage mode.",
    )
    parser.add_argument(
        "--session-id",
        help="Existing or new Session ID. Defaults to a generated opaque ID.",
    )
    return parser.parse_args(argv)


def _normalize_session_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _new_session_id() -> str:
    """生成不透明、不可预测且不会泄露本机路径的 Session ID。"""

    return f"session-{secrets.token_urlsafe(24)}"


def _redact_text(value: str) -> str:
    text = re.sub(r"Bearer\s+\S+", "Bearer <redacted>", value)
    return re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-<redacted>", text)


def _public_answer(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


if __name__ == "__main__":
    raise SystemExit(main())
