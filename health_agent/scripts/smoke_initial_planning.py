"""本地 INITIAL_PLANNING smoke 脚本。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.runtime.core import AgentCore
from agent.models.base import ProviderConfigurationError, ProviderResponseError
from agent.models.openai_compatible import OpenAICompatibleProvider


SAMPLE_PAYLOAD = {
    "userText": (
        "34岁，175cm，约93kg，肚子大。游泳25米都勉强，换气容易呛水，"
        "颈椎有问题，医生建议游泳。肌肉质量差，篮球两个回合就喘，"
        "血压135-145/85-95。目标是减脂、恢复体能、恢复基础力量。"
        "训练偏好是徒手为主，健身房辅助。"
    ),
    "profile": {
        "age": 34,
        "heightCm": 175,
        "weightKg": 93,
        "bloodPressureRange": "135-145/85-95",
    },
    "knownHealthConstraints": [
        {"name": "颈椎问题"},
        {"name": "游泳换气呛水风险"},
        {"name": "血压偏高倾向"},
    ],
    "goals": [
        {"name": "减脂"},
        {"name": "恢复体能"},
        {"name": "恢复基础力量"},
    ],
    "preferences": {
        "trainingMode": "徒手为主，健身房辅助",
    },
    "today": "2026-07-06",
}

MINIMAL_CONTRACT_PROMPT = """你是健康计划草案诊断模式。
只返回一个 JSON object，不要 markdown，不要解释。
字段必须且只需要包含：
- schemaVersion: "health-agent.initial-planning.minimal-diagnostic.v0"
- summary: 一句话说明这是待确认草案
- todayActionDraft: 保守、低强度、待确认的今日行动草案
- requiresUserConfirmation: true
不得声称已经保存、发布、确认或修改事实。
"""


def main() -> None:
    """运行一次首轮规划 smoke，并输出脱敏 AgentRunResult 摘要。"""
    args = _parse_args()
    _load_dotenv_file(PROJECT_ROOT / ".env")
    provider_name = _normalize_provider(
        args.provider or os.environ.get("REBOOT_HEALTH_AGENT_PROVIDER") or "mock"
    )
    debug_log = args.model_debug_log or _env_flag("REBOOT_HEALTH_MODEL_DEBUG_LOG")
    _configure_model_debug_logging(debug_log)
    try:
        provider = _build_provider(provider_name, debug_log=debug_log)
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

    if args.provider_ping:
        _run_provider_ping(provider, provider_name)
        return

    if args.contract_mode == "minimal":
        _run_minimal_contract(provider, provider_name)
        return

    result = AgentCore.default(provider=provider).run_detailed(
        "INITIAL_PLANNING",
        SAMPLE_PAYLOAD,
    )
    result_payload = result.to_dict()
    summary = (
        _redacted_draft_summary(result_payload, source_payload=SAMPLE_PAYLOAD)
        if args.print_draft_summary
        else _redacted_summary(result_payload)
    )
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
    parser.add_argument(
        "--print-draft-summary",
        action="store_true",
        help="Print a redacted draft summary for manual planning acceptance.",
    )
    parser.add_argument(
        "--model-debug-log",
        action="store_true",
        help="Enable redacted OpenAI-compatible provider diagnostic logs.",
    )
    parser.add_argument(
        "--provider-ping",
        action="store_true",
        help="Send a minimal OpenAI-compatible ping instead of running planning.",
    )
    parser.add_argument(
        "--contract-mode",
        choices=("minimal", "full"),
        default="full",
        help="Use full AgentLoop planning or a minimal provider-only JSON contract.",
    )
    return parser.parse_args()


def _load_dotenv_file(path: Path) -> tuple[str, ...]:
    """从 .env 读取缺失环境变量，已存在的 shell 环境变量优先。"""
    if not path.exists():
        return ()

    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)


def _parse_dotenv_line(raw_line: str) -> tuple[str, str] | None:
    """解析一行最小 dotenv 语法，避免引入额外生产依赖。"""
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return None

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    else:
        value = value.split(" #", 1)[0].rstrip()
    return key, value


def _normalize_provider(value: str) -> str:
    """规范化 provider 名称。"""
    normalized = value.strip().lower().replace("_", "-")
    if normalized in ("openai", "openai-compatible"):
        return "openai-compatible"
    return "mock"


def _build_provider(provider_name: str, debug_log: bool = False):
    """构造 smoke provider；默认 mock 通过 AgentCore.default 处理。"""
    if provider_name == "openai-compatible":
        return OpenAICompatibleProvider(debug_log=debug_log)
    return None


def _run_provider_ping(provider: object, provider_name: str) -> None:
    """执行极简 provider ping，并输出脱敏诊断摘要。"""
    if not isinstance(provider, OpenAICompatibleProvider):
        print(
            json.dumps(
                {
                    "provider": provider_name,
                    "status": "failed",
                    "responseOk": False,
                    "error": {
                        "code": "unsupported_provider",
                        "message": "provider-ping requires openai-compatible provider",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)

    started = time.monotonic()
    try:
        result = provider.ping()
    except ProviderResponseError as exc:
        print(
            json.dumps(
                _provider_failure_summary(
                    provider,
                    provider_name=provider_name,
                    elapsed_ms=_elapsed_ms(started),
                    error=exc,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(1)

    summary = {
        "provider": provider_name,
        "status": "ok",
        "elapsedMs": result.get("elapsedMs"),
        "responseOk": bool(result.get("ok")),
        "responseFormat": result.get("responseFormat"),
        "payloadBytes": result.get("payloadBytes"),
        "error": None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _run_minimal_contract(provider: object, provider_name: str) -> None:
    """执行 provider-only 的最小 JSON 合同诊断，不走完整 AgentLoop。"""
    if not isinstance(provider, OpenAICompatibleProvider):
        print(
            json.dumps(
                {
                    "provider": provider_name,
                    "status": "failed",
                    "contractMode": "minimal",
                    "error": {
                        "code": "unsupported_provider",
                        "message": "minimal contract requires openai-compatible provider",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)

    started = time.monotonic()
    try:
        output = provider.generate_json(
            MINIMAL_CONTRACT_PROMPT,
            _minimal_contract_payload(),
            temperature=0.2,
        )
    except ProviderResponseError as exc:
        print(
            json.dumps(
                {
                    **_provider_failure_summary(
                        provider,
                        provider_name=provider_name,
                        elapsed_ms=_elapsed_ms(started),
                        error=exc,
                    ),
                    "contractMode": "minimal",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(1)

    sensitive_texts = _sensitive_texts(SAMPLE_PAYLOAD)
    shape = provider.last_request_shape or {}
    summary = {
        "provider": provider_name,
        "status": "ok",
        "contractMode": "minimal",
        "responseFormat": getattr(provider, "response_format", None),
        "payloadBytes": shape.get("payloadBytes"),
        "outputKeys": sorted(str(key) for key in output.keys()),
        "requiresUserConfirmation": output.get("requiresUserConfirmation"),
        "hasTodayActionDraft": isinstance(output.get("todayActionDraft"), dict),
        "summaryPreview": _redacted_preview(
            output.get("summary"),
            sensitive_texts=sensitive_texts,
            max_string_length=120,
        ),
        "todayActionDraft": _redacted_preview(
            output.get("todayActionDraft"),
            sensitive_texts=sensitive_texts,
            max_depth=3,
        ),
        "error": None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _minimal_contract_payload() -> dict:
    """构造最小合同诊断输入，保留健康风险但不要求 weekly plan。"""
    return {
        "userText": SAMPLE_PAYLOAD["userText"],
        "profile": SAMPLE_PAYLOAD["profile"],
        "knownHealthConstraints": SAMPLE_PAYLOAD["knownHealthConstraints"],
        "goals": SAMPLE_PAYLOAD["goals"],
        "today": SAMPLE_PAYLOAD["today"],
    }


def _provider_failure_summary(
    provider: OpenAICompatibleProvider,
    provider_name: str,
    elapsed_ms: int,
    error: ProviderResponseError,
) -> dict:
    """输出不含 key/prompt/健康原文的 provider 失败摘要。"""
    shape = provider.last_request_shape or {}
    return {
        "provider": provider_name,
        "status": "failed",
        "elapsedMs": elapsed_ms,
        "responseOk": False,
        "responseFormat": getattr(provider, "response_format", None),
        "payloadBytes": shape.get("payloadBytes"),
        "error": _redacted_error(
            {
                "code": error.code or "provider_response_error",
                "message": error.safe_summary or str(error),
            }
        ),
    }


def _elapsed_ms(started: float) -> int:
    """返回耗时毫秒。"""
    return max(0, int((time.monotonic() - started) * 1000))


def _configure_model_debug_logging(enabled: bool) -> None:
    """开启标准错误输出上的模型诊断日志。"""
    if not enabled:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _env_flag(name: str) -> bool:
    """读取布尔环境开关。"""
    return str(os.environ.get(name) or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "debug",
    )


def _redacted_summary(result: dict) -> dict:
    """输出不包含 API key 和完整健康原文的 AgentRunResult 摘要。"""
    output = result.get("output") or {}
    trace = result.get("trace") or {}
    warnings = result.get("warnings") or []
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
        "warningCount": len(warnings),
        "qualityWarningCount": _quality_warning_count(warnings),
        "error": _redacted_error(result.get("error")),
    }


def _redacted_draft_summary(
    result: dict,
    source_payload: dict | None = None,
) -> dict:
    """输出人工验收用脱敏草案摘要，不包含完整 trace 或完整输入原文。"""
    summary = _redacted_summary(result)
    output = result.get("output") or {}
    sensitive_texts = _sensitive_texts(source_payload)
    warnings = result.get("warnings") or []
    summary.update(
        {
            "programDraft": _redacted_preview(
                output.get("programDraft"),
                sensitive_texts=sensitive_texts,
            ),
            "phaseDraft": _redacted_preview(
                output.get("phaseDraft"),
                sensitive_texts=sensitive_texts,
            ),
            "weeklyPlanDraft": _redacted_preview(
                output.get("weeklyPlanDraft"),
                sensitive_texts=sensitive_texts,
            ),
            "todayActionDraft": _redacted_preview(
                output.get("todayActionDraft"),
                sensitive_texts=sensitive_texts,
            ),
            "safetyNotes": _redacted_preview(
                output.get("safetyNotes"),
                sensitive_texts=sensitive_texts,
            ),
            "questions": _redacted_preview(
                output.get("questions"),
                sensitive_texts=sensitive_texts,
            ),
            "memoryCandidatesPreview": _memory_candidates_preview(
                result.get("memoryCandidates") or [],
                sensitive_texts=sensitive_texts,
            ),
            "warnings": _redacted_preview(
                warnings,
                sensitive_texts=sensitive_texts,
            ),
        }
    )
    return summary


def _quality_warning_count(warnings: object) -> int:
    """统计质量门禁 warning/error 数量，不输出具体健康内容。"""
    if not isinstance(warnings, list):
        return 0
    return sum(
        1
        for warning in warnings
        if isinstance(warning, str) and warning.startswith("quality:")
    )


def _memory_candidates_preview(
    candidates: object,
    sensitive_texts: tuple[str, ...],
) -> dict:
    """返回 memory candidates 的安全预览，不输出完整候选内容。"""
    if not isinstance(candidates, list):
        return {"count": 0, "items": []}
    items: list[dict] = []
    for candidate in candidates[:5]:
        if not isinstance(candidate, dict):
            continue
        preview = {
            "kind": candidate.get("kind"),
            "confidence": candidate.get("confidence"),
            "requiresUserConfirmation": candidate.get("requiresUserConfirmation"),
        }
        content = candidate.get("content")
        if content is not None:
            preview["contentPreview"] = _redacted_preview(
                content,
                sensitive_texts=sensitive_texts,
                max_depth=1,
                max_string_length=80,
            )
        items.append(preview)
    return {
        "count": len(candidates),
        "items": items,
        "truncatedItemCount": max(0, len(candidates) - len(items)),
    }


def _redacted_preview(
    value: object,
    sensitive_texts: tuple[str, ...] = (),
    max_depth: int = 5,
    max_list_items: int = 8,
    max_dict_items: int = 24,
    max_string_length: int = 180,
) -> object:
    """递归生成脱敏预览，限制深度、长度和列表规模。"""
    if max_depth < 0:
        return _type_summary(value)
    if isinstance(value, dict):
        preview: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_dict_items:
                preview["_truncatedKeys"] = len(value) - max_dict_items
                break
            key_text = str(key)
            if _is_sensitive_key(key_text):
                preview[key_text] = "<redacted>"
            else:
                preview[key_text] = _redacted_preview(
                    item,
                    sensitive_texts=sensitive_texts,
                    max_depth=max_depth - 1,
                    max_list_items=max_list_items,
                    max_dict_items=max_dict_items,
                    max_string_length=max_string_length,
                )
        return preview
    if isinstance(value, list):
        items = [
            _redacted_preview(
                item,
                sensitive_texts=sensitive_texts,
                max_depth=max_depth - 1,
                max_list_items=max_list_items,
                max_dict_items=max_dict_items,
                max_string_length=max_string_length,
            )
            for item in value[:max_list_items]
        ]
        if len(value) > max_list_items:
            items.append({"_truncatedItems": len(value) - max_list_items})
        return items
    if isinstance(value, tuple):
        return _redacted_preview(
            list(value),
            sensitive_texts=sensitive_texts,
            max_depth=max_depth,
            max_list_items=max_list_items,
            max_dict_items=max_dict_items,
            max_string_length=max_string_length,
        )
    if isinstance(value, str):
        return _truncate_text(
            _redact_sensitive_texts(_redact_text(value), sensitive_texts),
            max_string_length,
        )
    return value


def _type_summary(value: object) -> object:
    """深度超限时返回类型摘要，避免打印大型嵌套对象。"""
    if isinstance(value, dict):
        return {"_type": "object", "keyCount": len(value)}
    if isinstance(value, list):
        return {"_type": "list", "itemCount": len(value)}
    if isinstance(value, tuple):
        return {"_type": "list", "itemCount": len(value)}
    if isinstance(value, str):
        return _truncate_text(_redact_text(value), 80)
    return value


def _sensitive_texts(source_payload: dict | None) -> tuple[str, ...]:
    """提取本次 smoke 输入中不应原样输出的文本。"""
    if not isinstance(source_payload, dict):
        return ()
    values: list[str] = []
    user_text = str(source_payload.get("userText") or "").strip()
    if user_text:
        values.append(user_text)
    return tuple(values)


def _redact_sensitive_texts(value: str, sensitive_texts: tuple[str, ...]) -> str:
    """移除调用方传入的敏感原文。"""
    text = value
    for sensitive in sensitive_texts:
        if sensitive:
            text = text.replace(sensitive, "<redacted-health-input>")
    return text


def _truncate_text(value: str, max_length: int) -> str:
    """截断长文本，避免人工验收摘要变成完整原文 dump。"""
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}...<truncated>"


def _is_sensitive_key(key: str) -> bool:
    """识别不应输出的认证字段名。"""
    normalized = key.lower().replace("-", "_")
    sensitive_keys = {
        "api_key",
        "apikey",
        "authorization",
        "auth_token",
        "access_token",
        "refresh_token",
        "token",
        "secret",
        "client_secret",
        "password",
    }
    return (
        normalized in sensitive_keys
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
    )


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
