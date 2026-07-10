"""Health Agent 单次本地 console。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.bootstrap import create_generic_agent_loop_from_env
from agent.main import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    result_summary,
    run_user_text,
)
from agent.models import ProviderConfigurationError
from agent.runtime.generic_loop import GenericAgentLoop, GENERIC_STATUS_COMPLETED


def main(
    argv: Sequence[str] | None = None,
    *,
    loop_factory: Callable[[], GenericAgentLoop] = create_generic_agent_loop_from_env,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """运行一次通用 Agent 请求。"""
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    user_text = str(args.user_text or "").strip()
    if not user_text:
        print("error: --user-text is required", file=err)
        return EXIT_CONFIGURATION_ERROR

    try:
        loop = loop_factory()
        result = run_user_text(user_text, loop)
    except ProviderConfigurationError as exc:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "modelTurns": 0,
                    "toolCalls": 0,
                    "answer": None,
                    "error": {
                        "code": "missing_config",
                        "message": _redact_text(str(exc)),
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=err,
        )
        return EXIT_CONFIGURATION_ERROR

    print(json.dumps(result_summary(result), ensure_ascii=False, sort_keys=True), file=out)
    if result.status != GENERIC_STATUS_COMPLETED:
        return EXIT_RUNTIME_ERROR
    return EXIT_SUCCESS


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Health Agent generic loop once.")
    parser.add_argument("--user-text", help="User text for this one-shot run.")
    return parser.parse_args(argv)


def _redact_text(value: str) -> str:
    text = re.sub(r"Bearer\s+\S+", "Bearer <redacted>", value)
    return re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-<redacted>", text)


if __name__ == "__main__":
    raise SystemExit(main())
