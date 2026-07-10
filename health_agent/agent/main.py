"""Health Agent 通用本地入口。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from agent.bootstrap import create_generic_agent_loop_from_env
from agent.models import ProviderConfigurationError
from agent.runtime.generic_loop import (
    AgentRequest,
    GenericAgentLoop,
    GENERIC_STATUS_COMPLETED,
)
from agent.runtime.result import AgentRunResult

DEFAULT_USER_TEXT = "190 斤是多少公斤？请调用可用的重量转换工具，不要自行心算。"
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONFIGURATION_ERROR = 2


def run_user_text(user_text: str, loop: GenericAgentLoop) -> AgentRunResult:
    """运行一次通用 Agent 请求。"""
    return loop.run(AgentRequest(user_text=user_text))


def main(
    argv: Sequence[str] | None = None,
    *,
    loop_factory: Callable[[], GenericAgentLoop] = create_generic_agent_loop_from_env,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """执行一次通用 Agent run，并返回进程退出码。"""
    args = _parse_args(argv)
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    user_text = args.user_text.strip() if args.user_text else DEFAULT_USER_TEXT

    try:
        loop = loop_factory()
        result = run_user_text(user_text, loop)
    except ProviderConfigurationError as exc:
        print(
            json.dumps(
                _error_summary(
                    status="configuration_error",
                    code="missing_config",
                    message=str(exc),
                ),
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=err,
        )
        return EXIT_CONFIGURATION_ERROR

    summary = result_summary(result)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True), file=out)
    if result.status != GENERIC_STATUS_COMPLETED:
        return EXIT_RUNTIME_ERROR
    return EXIT_SUCCESS


def result_summary(result: AgentRunResult) -> dict[str, object]:
    """生成安全运行摘要，不包含完整 prompt、消息历史或 raw response。"""
    payload: dict[str, object] = {
        "status": result.status,
        "modelTurns": result.model_turns,
        "toolCalls": result.tool_calls,
        "finishReason": result.finish_reason,
        "answer": _public_answer(result.final_text),
    }
    if result.error is not None:
        payload["error"] = {
            "code": result.error.code,
            "message": _redact_text(result.error.message),
        }
    return payload


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Health Agent generic loop once.")
    parser.add_argument(
        "--user-text",
        help="User text for this one-shot run. Defaults to a weight conversion prompt.",
    )
    return parser.parse_args(argv)


def _error_summary(status: str, code: str, message: str) -> dict[str, object]:
    return {
        "status": status,
        "modelTurns": 0,
        "toolCalls": 0,
        "answer": None,
        "error": {
            "code": code,
            "message": _redact_text(message),
        },
    }


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
