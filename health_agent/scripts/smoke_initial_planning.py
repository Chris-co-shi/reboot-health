"""本地 INITIAL_PLANNING smoke 脚本。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.runtime.core import AgentCore
from agent.models.base import ProviderConfigurationError
from agent.models.openai_compatible import OpenAICompatibleProvider


SAMPLE_PAYLOAD = {
    "userText": "体能差，游泳容易呛水，血压有点高，想从低强度恢复训练。",
    "today": "2026-07-06",
}


def main() -> None:
    """运行一次首轮规划 smoke，并输出脱敏 AgentRunResult 摘要。"""
    args = _parse_args()
    provider_name = _normalize_provider(
        args.provider or os.environ.get("REBOOT_HEALTH_AGENT_PROVIDER") or "mock"
    )
    try:
        provider = _build_provider(provider_name)
    except ProviderConfigurationError as exc:
        print(
            json.dumps(
                {
                    "schemaVersion": "health-agent.run.v0",
                    "status": "failed",
                    "finalOutcome": "failed",
                    "provider": provider_name,
                    "error": {
                        "code": "missing_config",
                        "message": str(exc),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)

    result = AgentCore.default(provider=provider).run_detailed(
        "INITIAL_PLANNING",
        SAMPLE_PAYLOAD,
    )
    summary = _redacted_summary(result.to_dict())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("error"):
        raise SystemExit(1)


def _parse_args() -> argparse.Namespace:
    """读取 smoke 参数。"""
    parser = argparse.ArgumentParser(description="Run INITIAL_PLANNING smoke test.")
    parser.add_argument(
        "--provider",
        choices=("mock", "openai-compatible"),
        help="Provider to use. Defaults to REBOOT_HEALTH_AGENT_PROVIDER or mock.",
    )
    return parser.parse_args()


def _normalize_provider(value: str) -> str:
    """规范化 provider 名称。"""
    normalized = value.strip().lower().replace("_", "-")
    if normalized in ("openai", "openai-compatible"):
        return "openai-compatible"
    return "mock"


def _build_provider(provider_name: str):
    """构造 smoke provider；默认 mock 通过 AgentCore.default 处理。"""
    if provider_name == "openai-compatible":
        return OpenAICompatibleProvider()
    return None


def _redacted_summary(result: dict) -> dict:
    """输出不包含 API key 和完整健康原文的 AgentRunResult 摘要。"""
    output = result.get("output") or {}
    trace = result.get("trace") or {}
    return {
        "schemaVersion": result.get("schemaVersion"),
        "runId": result.get("runId"),
        "sessionId": result.get("sessionId"),
        "status": result.get("status"),
        "selectedSkill": result.get("selectedSkill"),
        "finalOutcome": result.get("finalOutcome"),
        "provider": trace.get("provider"),
        "outputSchemaVersion": output.get("schemaVersion"),
        "requiresUserConfirmation": output.get("requiresUserConfirmation"),
        "hasProgramDraft": isinstance(output.get("programDraft"), dict),
        "hasWeeklyPlanDraft": isinstance(output.get("weeklyPlanDraft"), dict),
        "hasTodayActionDraft": isinstance(output.get("todayActionDraft"), dict),
        "memoryCandidateCount": len(result.get("memoryCandidates") or []),
        "warningCount": len(result.get("warnings") or []),
        "error": _redacted_error(result.get("error")),
    }


def _redacted_error(error: object) -> object:
    """脱敏错误消息。"""
    if not isinstance(error, dict):
        return error
    redacted = dict(error)
    if "message" in redacted:
        redacted["message"] = _redact_text(str(redacted["message"]))
    return redacted


def _redact_text(value: str) -> str:
    """移除可能的 token/API key 片段。"""
    text = re.sub(r"Bearer\s+\S+", "Bearer <redacted>", value)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-<redacted>", text)
    configured_key = os.environ.get("REBOOT_HEALTH_MODEL_API_KEY")
    if configured_key:
        text = text.replace(configured_key, "<redacted>")
    legacy_key = os.environ.get("AGENT_OPENAI_API_KEY")
    if legacy_key:
        text = text.replace(legacy_key, "<redacted>")
    return text


if __name__ == "__main__":
    main()
