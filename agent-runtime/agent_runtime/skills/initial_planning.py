from __future__ import annotations

from importlib import resources
from typing import Any, Mapping

from agent_runtime.providers.base import BaseModelProvider
from agent_runtime.providers.mock import MockProvider
from agent_runtime.schema import (
    PLANNING_SCHEMA_VERSION,
    PlanningInput,
    PlanningOutput,
    SchemaValidationError,
    validate_planning_output,
)


FORBIDDEN_BUSINESS_FACT_CLAIMS = (
    "已保存",
    "保存成功",
    "已发布",
    "发布成功",
    "已确认",
    "确认成功",
    "已生效",
    "已经生效",
    "已写入",
    "写入数据库",
    "已更新业务事实",
    "已修改业务事实",
)


class InitialPlanningSkill:
    trigger = "INITIAL_PLANNING"

    def __init__(self, provider: BaseModelProvider | None = None) -> None:
        self.provider = provider or MockProvider()

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        planning_input = PlanningInput.from_mapping(payload)
        provider_output = self.provider.generate_initial_planning(
            _load_prompt(),
            planning_input.to_provider_payload(),
        )
        output = PlanningOutput.from_mapping(provider_output).to_dict()
        output = self._apply_runtime_boundaries(output)
        output = validate_planning_output(output)
        self._assert_no_forbidden_business_fact_claims(output)
        return output

    def _apply_runtime_boundaries(self, output: dict[str, Any]) -> dict[str, Any]:
        output["schemaVersion"] = PLANNING_SCHEMA_VERSION
        output["requiresUserConfirmation"] = True

        for key in ("programDraft", "phaseDraft", "weeklyPlanDraft", "todayActionDraft"):
            draft = output.get(key)
            if isinstance(draft, dict):
                draft.setdefault("status", "draft_requires_confirmation")
            else:
                output[key] = {"status": "draft_requires_confirmation"}

        notes = output.setdefault("safetyNotes", [])
        if isinstance(notes, list):
            runtime_note = "Python runtime 只生成候选和草案；事实保存、安全规则、确认和发布由 Java 后续流程处理。"
            if runtime_note not in notes:
                notes.insert(0, runtime_note)
        return output

    def _assert_no_forbidden_business_fact_claims(
        self,
        output: Mapping[str, Any],
    ) -> None:
        text = _flatten_text(output)
        for phrase in FORBIDDEN_BUSINESS_FACT_CLAIMS:
            if phrase in text:
                raise SchemaValidationError(
                    f"Planning output contains forbidden business fact claim: {phrase}"
                )


def _load_prompt() -> str:
    return (
        resources.files("agent_runtime.prompts")
        .joinpath("initial_planning_zh.md")
        .read_text(encoding="utf-8")
    )


def _flatten_text(value: Any) -> str:
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
