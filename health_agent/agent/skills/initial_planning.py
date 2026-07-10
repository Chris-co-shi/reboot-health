"""INITIAL_PLANNING Skill。

该 Skill 把用户自然语言和少量上下文转成健康理解候选、约束候选、目标候选、计划
草案和今日行动草案。它只生成待确认结果，不保存事实、不发布计划。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Mapping

from agent.models import (
    ModelMessage,
    ModelOptions,
    ModelProvider,
    ProviderResponseError,
)
from agent.safety.rules import FORBIDDEN_BUSINESS_FACT_CLAIMS
from agent.schemas.planning import (
    ALLOWED_DRAFT_STATUSES,
    DRAFT_STATUS_DRAFT_REQUIRES_CONFIRMATION,
    DRAFT_STATUS_INSUFFICIENT_INFORMATION,
    PLANNING_SCHEMA_VERSION,
    PlanningInput,
    PlanningOutput,
    SchemaValidationError,
    validate_planning_output,
)


LOGGER = logging.getLogger(__name__)


class InitialPlanningSkill:
    """首轮规划兼容 Skill，负责生成 INITIAL_PLANNING v0 草案。

    这是通用 Model Turn Contract 落地期间的临时迁移层；Provider 不再理解
    INITIAL_PLANNING，本 Skill 负责旧 prompt/input/output 的兼容转换。
    """

    trigger = "INITIAL_PLANNING"

    def __init__(self, provider: ModelProvider) -> None:
        """创建 Skill；Provider 必须由产品 Bootstrap 或测试显式注入。"""
        self.provider = provider
        self.last_trace_steps: list[dict[str, Any]] = []

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """执行首轮规划流程。

        流程顺序固定为：输入规范化 -> Provider 生成草案 -> 输出规范化 -> 运行时
        安全边界覆盖 -> Schema 校验 -> 禁止业务事实声明检查。
        """
        self.last_trace_steps = []
        planning_input = PlanningInput.from_mapping(payload)
        provider_payload = planning_input.to_provider_payload()
        _debug_trace(
            "skill_input_normalized",
            providerPayloadKeys=sorted(str(key) for key in provider_payload.keys()),
            userTextChars=len(planning_input.userText),
        )

        prompt_path = _prompt_path()
        prompt = prompt_path.read_text(encoding="utf-8")
        _debug_trace(
            "skill_prompt_loaded",
            promptChars=len(prompt),
            promptPath=str(prompt_path),
        )

        provider_started = time.monotonic()
        model_response = self.provider.complete_turn(
            messages=(
                ModelMessage(role="system", content=prompt),
                ModelMessage(
                    role="user",
                    content=json.dumps(provider_payload, ensure_ascii=False),
                ),
            ),
            tools=(),
            options=ModelOptions(temperature=0.2),
        )
        if model_response.tool_calls:
            raise ProviderResponseError(
                "INITIAL_PLANNING compatibility layer does not support model tool calls",
                code="tool_calls_not_supported",
                safe_summary=(
                    "INITIAL_PLANNING compatibility layer does not support model tool calls"
                ),
            )
        provider_output = _parse_model_json_content(model_response.content)
        provider_elapsed_ms = _elapsed_ms(provider_started)
        provider_meta = _provider_trace_metadata(self.provider)
        self._record_trace_step(
            "provider_request_sent",
            elapsedMs=provider_elapsed_ms,
            **provider_meta,
            payloadBytes=_provider_payload_bytes(self.provider, provider_payload),
        )
        self._record_trace_step(
            "provider_response_received",
            elapsedMs=provider_elapsed_ms,
            **provider_meta,
            contentChars=_content_chars(provider_output),
        )
        self._record_trace_step(
            "provider_json_parsed",
            **provider_meta,
            topLevelKeys=_top_level_keys(provider_output),
            fieldTypes=_field_types(provider_output),
        )
        _debug_trace(
            "skill_provider_output_received",
            topLevelKeys=_top_level_keys(provider_output),
            fieldTypes=_field_types(provider_output),
            todayActionDraftType=_field_type(provider_output, "todayActionDraft"),
        )
        self._record_trace_step(
            "skill_provider_output_received",
            topLevelKeys=_top_level_keys(provider_output),
            fieldTypes=_field_types(provider_output),
        )

        today_action_source, today_action_missing_fields = (
            _today_action_draft_diagnostics(
                provider_output.get("todayActionDraft")
                if isinstance(provider_output, Mapping)
                else None
            )
        )

        output = PlanningOutput.from_mapping(provider_output).to_dict()
        _debug_trace(
            "skill_output_mapped",
            fieldTypes=_field_types(output),
        )
        self._record_trace_step(
            "skill_output_mapped",
            topLevelKeys=_top_level_keys(output),
            fieldTypes=_field_types(output),
        )

        output = self._apply_runtime_boundaries(output, planning_input)
        _debug_trace(
            "runtime_boundaries_applied",
            fieldTypes=_field_types(output),
            todayActionDraftSource=today_action_source,
            todayActionDraftMissingFields=today_action_missing_fields,
        )
        self._record_trace_step(
            "runtime_boundaries_applied",
            fieldTypes=_field_types(output),
            todayActionDraftSource=today_action_source,
            todayActionDraftMissingFields=today_action_missing_fields,
        )

        output = validate_planning_output(output)
        _debug_trace(
            "skill_schema_validated",
            fieldTypes=_field_types(output),
        )
        self._record_trace_step(
            "schema_validated",
            topLevelKeys=_top_level_keys(output),
            fieldTypes=_field_types(output),
        )

        self._assert_no_forbidden_business_fact_claims(output)
        _debug_trace(
            "skill_forbidden_claims_checked",
            topLevelKeys=_top_level_keys(output),
        )
        return output

    def _record_trace_step(self, name: str, **fields: Any) -> None:
        """记录给 AgentLoop 合并进 RunTrace 的结构化摘要。"""
        self.last_trace_steps.append({"name": name, **fields})

    def _apply_runtime_boundaries(
        self,
        output: dict[str, Any],
        planning_input: PlanningInput,
    ) -> dict[str, Any]:
        """强制写入运行时边界，防止 Provider 输出越权。

        无论 Provider 返回什么，当前阶段都必须使用 v0 schema，并要求用户确认。
        草案类字段只能是待确认草案或信息不足草案。
        """
        output["schemaVersion"] = PLANNING_SCHEMA_VERSION
        output["requiresUserConfirmation"] = True

        output["programDraft"] = _ensure_draft_contract(output.get("programDraft"))
        output["phaseDraft"] = _ensure_draft_contract(output.get("phaseDraft"))
        output["weeklyPlanDraft"] = _ensure_weekly_draft_contract(
            output.get("weeklyPlanDraft")
        )
        output["todayActionDraft"] = _ensure_today_action_contract(
            output.get("todayActionDraft")
        )

        self._remove_contradictory_unknown_profile_candidates(output, planning_input)
        output.setdefault("safetyNotes", [])
        output.setdefault("questions", [])
        return output

    def _remove_contradictory_unknown_profile_candidates(
        self,
        output: dict[str, Any],
        planning_input: PlanningInput,
    ) -> None:
        """输入已有年龄/身高/体重时，移除对应 unknown 候选。"""
        present = _profile_presence(planning_input)
        for key in (
            "understandingCandidates",
            "healthConstraintCandidates",
            "goalCandidates",
        ):
            items = output.get(key)
            if not isinstance(items, list):
                continue
            output[key] = [
                item for item in items if not _contradicts_profile_presence(item, present)
            ]

    def _assert_no_forbidden_business_fact_claims(
        self,
        output: Mapping[str, Any],
    ) -> None:
        """禁止输出宣称已经保存、发布、确认或写入业务事实。"""
        text = _flatten_text(output)
        for phrase in FORBIDDEN_BUSINESS_FACT_CLAIMS:
            if phrase in text:
                raise SchemaValidationError(
                    f"Planning output contains forbidden business fact claim: {phrase}"
                )


def _load_prompt() -> str:
    """读取 INITIAL_PLANNING 的中文 Prompt 资产。"""
    return _prompt_path().read_text(encoding="utf-8")


def _prompt_path() -> Path:
    """返回 INITIAL_PLANNING Prompt 路径。"""
    project_root = Path(__file__).resolve().parents[2]
    return (
        project_root
        .joinpath("skills", "initial_planning", "prompt.zh-CN.md")
    )


def _parse_model_json_content(content: str | None) -> Mapping[str, Any]:
    """从通用 ModelResponse.content 中解析 INITIAL_PLANNING JSON 对象。"""
    if not str(content or "").strip():
        raise ProviderResponseError(
            "INITIAL_PLANNING model response content is empty",
            code="invalid_json",
            safe_summary="INITIAL_PLANNING model response content is empty",
        )
    try:
        parsed = _extract_json_object(str(content))
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        raise ProviderResponseError(
            "INITIAL_PLANNING model response content is not a valid JSON object",
            code="invalid_json",
            safe_summary="INITIAL_PLANNING model response content is not a valid JSON object",
        ) from exc
    return parsed


def _extract_json_object(text: str) -> Mapping[str, Any]:
    """提取模型文本中的第一个 JSON object。"""
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                parsed = json.loads(text[start : index + 1])
                if not isinstance(parsed, Mapping):
                    raise ValueError("JSON value must be an object")
                return dict(parsed)
    raise ValueError("No complete JSON object found")


def _debug_trace(event: str, **fields: Any) -> None:
    """按环境开关输出 Skill 阶段诊断日志。"""
    if not _debug_trace_enabled():
        return
    payload = {"event": event, **fields}
    LOGGER.info(
        "initial_planning_skill %s",
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def _debug_trace_enabled() -> bool:
    """读取 Skill debug trace 开关。"""
    return str(os.environ.get("REBOOT_HEALTH_AGENT_DEBUG_TRACE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "debug",
    )


def _top_level_keys(value: Any) -> list[str]:
    """返回顶层字段名。"""
    if not isinstance(value, Mapping):
        return []
    return sorted(str(key) for key in value.keys())


def _field_types(value: Any) -> dict[str, str]:
    """返回顶层字段类型。"""
    if not isinstance(value, Mapping):
        return {}
    return {str(key): type(item).__name__ for key, item in value.items()}


def _field_type(value: Any, key: str) -> str:
    """返回指定字段类型。"""
    if not isinstance(value, Mapping):
        return "NoneType"
    return type(value.get(key)).__name__


def _provider_trace_metadata(provider: ModelProvider) -> dict[str, Any]:
    """返回 Provider 的非敏感 trace 元数据。"""
    provider_name = getattr(provider, "provider_name", None) or "unknown"
    model = getattr(provider, "model", None) or provider_name
    return {
        "provider": str(provider_name),
        "model": str(model),
    }


def _provider_payload_bytes(
    provider: ModelProvider,
    provider_payload: Mapping[str, Any],
) -> int:
    """读取 Provider request payload 字节数；没有原生 shape 时用输入摘要估算。"""
    shape = getattr(provider, "last_request_shape", None)
    if isinstance(shape, Mapping):
        payload_bytes = shape.get("payloadBytes")
        if isinstance(payload_bytes, int):
            return payload_bytes
    return len(json.dumps(provider_payload, ensure_ascii=False, default=str).encode("utf-8"))


def _content_chars(value: Any) -> int:
    """返回 Provider 解析后输出的字符规模摘要。"""
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _elapsed_ms(started: float) -> int:
    """返回耗时毫秒。"""
    return max(0, int((time.monotonic() - started) * 1000))


def _today_action_draft_diagnostics(draft: Any) -> tuple[str, list[str]]:
    """判断 todayActionDraft 的 provider 原生形状。"""
    if not isinstance(draft, Mapping):
        return "provider_invalid_empty_draft", ["status", "actions"]
    missing_fields = []
    if not str(draft.get("status") or "").strip():
        missing_fields.append("status")
    if "actions" not in draft:
        missing_fields.append("actions")
    if missing_fields:
        return "provider_dict_missing_structural_fields", missing_fields
    return "provider_dict_preserved", []


def _ensure_draft_contract(draft: Any) -> dict[str, Any]:
    """保留草案对象，只补结构状态，不生成业务内容。"""
    result = dict(draft) if isinstance(draft, Mapping) else {}
    status = str(result.get("status") or "").strip()
    if not status:
        result["status"] = DRAFT_STATUS_INSUFFICIENT_INFORMATION
        return result
    if status not in ALLOWED_DRAFT_STATUSES:
        raise SchemaValidationError(
            "draft.status must be draft_requires_confirmation or insufficient_information"
        )
    result["status"] = status
    return result


def _ensure_weekly_draft_contract(draft: Any) -> dict[str, Any]:
    """保留 WeeklyPlanDraft；信息不足时允许空 days。"""
    result = _ensure_draft_contract(draft)
    days = result.get("days")
    if days is None:
        result["days"] = []
    elif not isinstance(days, list):
        raise SchemaValidationError("weeklyPlanDraft.days must be a list")
    return result


def _ensure_today_action_contract(draft: Any) -> dict[str, Any]:
    """保留 TodayActionDraft；信息不足时允许空 actions。"""
    result = _ensure_draft_contract(draft)
    actions = result.get("actions")
    if actions is None:
        result["actions"] = []
    elif not isinstance(actions, list):
        raise SchemaValidationError("todayActionDraft.actions must be a list")
    return result


def _flatten_text(value: Any) -> str:
    """递归展开输出内容，供禁止短语检查使用。"""
    parts: list[str] = []
    if isinstance(value, Mapping):
        for key in sorted(value.keys(), key=str):
            parts.append(str(key))
            parts.append(_flatten_text(value[key]))
    elif isinstance(value, list | tuple | set):
        for item in value:
            parts.append(_flatten_text(item))
    elif value is not None:
        parts.append(str(value))
    return "\n".join(part for part in parts if part)


def _profile_presence(planning_input: PlanningInput) -> dict[str, bool]:
    """判断输入是否已经包含年龄、身高、体重。"""
    profile = planning_input.profile
    text = planning_input.userText
    return {
        "age": bool(profile.get("age")) or bool(re.search(r"\d+\s*岁", text)),
        "height": bool(profile.get("heightCm") or profile.get("height")) or bool(
            re.search(r"\d+\s*(?:cm|厘米)", text, flags=re.IGNORECASE)
        ),
        "weight": bool(profile.get("weightKg") or profile.get("weight")) or bool(
            re.search(r"\d+\s*(?:kg|公斤)", text, flags=re.IGNORECASE)
        ),
    }


def _contradicts_profile_presence(item: Any, present: Mapping[str, bool]) -> bool:
    """判断候选是否与已提供 profile 信息矛盾。"""
    text = _flatten_text(item).lower()
    if "unknown_age_weight_height" in text and all(present.values()):
        return True
    checks = {
        "age": ("年龄未知", "未提供年龄", "unknown_age", "age unknown"),
        "height": ("身高未知", "未提供身高", "unknown_height", "height unknown"),
        "weight": ("体重未知", "未提供体重", "unknown_weight", "weight unknown"),
    }
    for key, phrases in checks.items():
        if present.get(key) and any(phrase.lower() in text for phrase in phrases):
            return True
    return False
