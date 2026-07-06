"""INITIAL_PLANNING Skill。

该 Skill 把用户自然语言和少量上下文转成健康理解候选、约束候选、目标候选、计划
草案和今日行动草案。它只生成待确认结果，不保存事实、不发布计划，也不绕过 Java
Domain Kernel 的安全与确认边界。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from agent.models.base import BaseModelProvider
from agent.models.mock import MockProvider
from agent.safety.rules import FORBIDDEN_BUSINESS_FACT_CLAIMS
from agent.schemas.planning import (
    PLANNING_SCHEMA_VERSION,
    PlanningInput,
    PlanningOutput,
    SchemaValidationError,
    validate_planning_output,
)


class InitialPlanningSkill:
    """首轮规划 Skill，负责生成 INITIAL_PLANNING v0 草案。"""

    trigger = "INITIAL_PLANNING"

    def __init__(self, provider: BaseModelProvider | None = None) -> None:
        """创建 Skill，并默认使用 MockProvider 保持本地可测。"""
        self.provider = provider or MockProvider()

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """执行首轮规划流程。

        流程顺序固定为：输入规范化 -> Provider 生成草案 -> 输出规范化 -> 运行时
        安全边界覆盖 -> Schema 校验 -> 禁止业务事实声明检查。
        """
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
        """强制写入运行时边界，防止 Provider 输出越权。

        无论 Provider 返回什么，当前阶段都必须使用 v0 schema，并要求用户确认。
        草案类字段也必须保持 `draft_requires_confirmation` 状态。
        """
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
            # 这条说明是运行时边界，不依赖 Prompt 或模型是否主动提到。
            runtime_note = "Python runtime 只生成候选和草案；事实保存、安全规则、确认和发布由 Java 后续流程处理。"
            if runtime_note not in notes:
                notes.insert(0, runtime_note)
        return output

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
    project_root = Path(__file__).resolve().parents[2]
    return (
        project_root
        .joinpath("skills", "initial_planning", "prompt.zh-CN.md")
        .read_text(encoding="utf-8")
    )


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
