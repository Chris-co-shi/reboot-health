"""INITIAL_PLANNING eval runner。

该脚本执行固定 offline eval case，验证 single-shot INITIAL_PLANNING 的合同、
安全边界和 trace 摘要。它不接数据库、不接 Java、不调用真实模型，也不保存任何
模型输出。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.runtime.core import AgentCore
from scripts.smoke_initial_planning import (
    _apply_diagnostic_defaults,
    _load_dotenv_file,
    _redacted_trace,
)

CASES_DIR = PROJECT_ROOT / "tests" / "evals" / "initial_planning_cases"


def main() -> None:
    """运行 INITIAL_PLANNING eval cases。"""
    args = _parse_args()
    _load_dotenv_file(PROJECT_ROOT / ".env")
    _apply_diagnostic_defaults()
    provider = build_provider(args.provider)
    cases = load_eval_cases()
    summary = run_eval_cases(
        cases,
        provider=provider,
        print_trace=args.print_trace,
        fail_fast=args.fail_fast,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


def _parse_args() -> argparse.Namespace:
    """读取 eval runner 参数。"""
    parser = argparse.ArgumentParser(description="Run INITIAL_PLANNING eval cases.")
    parser.add_argument(
        "--provider",
        choices=("mock",),
        default="mock",
        help="Provider to use for offline eval cases. Only mock is allowed.",
    )
    parser.add_argument(
        "--print-trace",
        action="store_true",
        help="Include redacted trace summary for each eval case.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed eval case.",
    )
    return parser.parse_args()


def load_eval_cases(cases_dir: Path = CASES_DIR) -> list[dict[str, Any]]:
    """读取 eval case JSON 文件。"""
    cases: list[dict[str, Any]] = []
    for path in sorted(cases_dir.glob("*.json")):
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


def build_provider(provider_name: str) -> object | None:
    """构造 eval provider；offline eval 只允许 mock。"""
    if provider_name != "mock":
        raise ValueError("offline eval runner only supports mock provider")
    return None


def run_eval_cases(
    cases: list[Mapping[str, Any]],
    provider: object | None = None,
    print_trace: bool = False,
    fail_fast: bool = False,
) -> dict[str, Any]:
    """运行一组 eval cases 并汇总结果。"""
    results: list[dict[str, Any]] = []
    for case in cases:
        result = run_eval_case(case, provider=provider, print_trace=print_trace)
        results.append(result)
        if fail_fast and not result["passed"]:
            break
    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def run_eval_case(
    case: Mapping[str, Any],
    provider: object | None = None,
    print_trace: bool = False,
) -> dict[str, Any]:
    """运行单个 eval case。"""
    agent_result = AgentCore.default(provider=provider).run_detailed(
        "INITIAL_PLANNING",
        case.get("input") if isinstance(case.get("input"), Mapping) else {},
    )
    payload = agent_result.to_dict()
    failures = evaluate_result(case, payload)
    result: dict[str, Any] = {
        "name": str(case.get("name") or "unnamed"),
        "passed": not failures,
        "failures": failures,
        "finalOutcome": payload.get("finalOutcome"),
        "requiresUserConfirmation": (payload.get("output") or {}).get(
            "requiresUserConfirmation"
        ),
        "warningCount": len(payload.get("warnings") or []),
        "error": payload.get("error"),
    }
    if print_trace:
        result["trace"] = _redacted_trace(
            payload.get("trace"),
            source_payload=case.get("input") if isinstance(case.get("input"), dict) else None,
        )
    return result


def evaluate_result(case: Mapping[str, Any], result: Mapping[str, Any]) -> list[str]:
    """按 case expected 检查 AgentRunResult。"""
    expected = case.get("expected") if isinstance(case.get("expected"), Mapping) else {}
    output = result.get("output") if isinstance(result.get("output"), Mapping) else {}
    failures: list[str] = []

    if result.get("error") is not None:
        failures.append("error_must_be_null")
    if expected.get("finalOutcome") and result.get("finalOutcome") != expected.get(
        "finalOutcome"
    ):
        failures.append("finalOutcome_mismatch")
    if output.get("requiresUserConfirmation") is not expected.get(
        "requiresUserConfirmation"
    ):
        failures.append("requiresUserConfirmation_mismatch")
    if expected.get("mustHaveTodayActionDraft") and not isinstance(
        output.get("todayActionDraft"),
        Mapping,
    ):
        failures.append("todayActionDraft_missing")
    if expected.get("mustHaveSafetyNotes") and not _non_empty_list(
        output.get("safetyNotes")
    ):
        failures.append("safetyNotes_missing")

    today_action = output.get("todayActionDraft")
    if isinstance(today_action, Mapping):
        for field in expected.get("requiredTodayActionFields") or []:
            if not _field_present(today_action, str(field)):
                failures.append(f"todayActionDraft.{field}_missing")

    text = _flatten_text(output)
    for phrase in expected.get("forbiddenPhrases") or []:
        if str(phrase) and str(phrase) in text:
            failures.append(f"forbidden_phrase:{phrase}")
    return failures


def _field_present(value: Mapping[str, Any], field: str) -> bool:
    """判断字段是否存在且非空。"""
    item = value.get(field)
    if isinstance(item, list):
        return bool(item)
    if isinstance(item, Mapping):
        return bool(item)
    return bool(str(item or "").strip())


def _non_empty_list(value: Any) -> bool:
    """判断非空 list。"""
    return isinstance(value, list) and bool(value)


def _flatten_text(value: Any) -> str:
    """展开输出文本用于 forbidden phrase 检查。"""
    parts: list[str] = []
    if isinstance(value, Mapping):
        for key in sorted(value.keys(), key=str):
            parts.append(str(key))
            parts.append(_flatten_text(value[key]))
    elif isinstance(value, list | tuple):
        for item in value:
            parts.append(_flatten_text(item))
    elif value is not None:
        parts.append(str(value))
    return "\n".join(part for part in parts if part)


if __name__ == "__main__":
    main()
