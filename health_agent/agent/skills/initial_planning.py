"""INITIAL_PLANNING Skill。

该 Skill 把用户自然语言和少量上下文转成健康理解候选、约束候选、目标候选、计划
草案和今日行动草案。它只生成待确认结果，不保存事实、不发布计划，也不绕过 Java
Domain Kernel 的安全与确认边界。
"""

from __future__ import annotations

import re
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
        output = self._apply_runtime_boundaries(output, planning_input)
        output = validate_planning_output(output)
        self._assert_no_forbidden_business_fact_claims(output)
        return output

    def _apply_runtime_boundaries(
        self,
        output: dict[str, Any],
        planning_input: PlanningInput,
    ) -> dict[str, Any]:
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

        self._remove_contradictory_unknown_profile_candidates(output, planning_input)
        output["todayActionDraft"] = self._ensure_today_action_contract(
            output.get("todayActionDraft"),
            planning_input,
        )
        output["questions"] = self._ensure_questions_contract(output)

        notes = output.setdefault("safetyNotes", [])
        if isinstance(notes, list):
            # 这条说明是运行时边界，不依赖 Prompt 或模型是否主动提到。
            runtime_note = "Python runtime 只生成候选和草案；事实保存、安全规则、确认和发布由 Java 后续流程处理。"
            if runtime_note not in notes:
                notes.insert(0, runtime_note)
        return output

    def _ensure_today_action_contract(
        self,
        draft: Any,
        planning_input: PlanningInput,
    ) -> dict[str, Any]:
        """补齐 TodayActionDraft 最小合同。

        真实模型有时只返回 status。这里用低风险 fallback 补齐可执行的今日行动，
        仍保持草案和待确认状态。
        """
        result = dict(draft) if isinstance(draft, Mapping) else {}
        fallback = _safe_today_action_fallback(planning_input)
        result["status"] = "draft_requires_confirmation"
        result["title"] = str(
            result.get("title") or result.get("name") or fallback["title"]
        )
        if not _non_empty_list(result.get("actions")):
            result["actions"] = fallback["actions"]
        if not str(result.get("minimumCompletionStandard") or "").strip():
            result["minimumCompletionStandard"] = fallback[
                "minimumCompletionStandard"
            ]
        if not (
            str(result.get("downgradeRule") or "").strip()
            or _non_empty_list(result.get("downgradeOptions"))
        ):
            result["downgradeRule"] = fallback["downgradeRule"]
        if not _non_empty_list(result.get("stopConditions")):
            result["stopConditions"] = fallback["stopConditions"]
        if not _non_empty_list(result.get("feedbackFields")):
            result["feedbackFields"] = fallback["feedbackFields"]
        if not _non_empty_list(result.get("exclusions")):
            result["exclusions"] = fallback["exclusions"]
        return result

    def _ensure_questions_contract(self, output: Mapping[str, Any]) -> list[str]:
        """当输出声明关键信息缺失时补 1-3 个关键追问。"""
        existing = [
            str(item).strip()
            for item in output.get("questions", [])
            if str(item).strip()
        ]
        if existing:
            return existing

        markers = _missing_info_markers(_flatten_text(output))
        questions: list[str] = []
        if {"age", "height", "weight"} & markers:
            questions.append("请确认年龄、身高、体重和近期体重变化范围。")
        if "medication" in markers:
            questions.append("近期是否使用降压药或其他影响运动安全的药物？")
        if {"venue", "equipment"} & markers:
            questions.append("本周可用场地、器械和每次可训练时间是什么？")
        if "doctor_limit" in markers:
            questions.append("医生是否给出游泳、颈椎或血压相关的运动限制？")
        return questions[:3]

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


def _safe_today_action_fallback(planning_input: PlanningInput) -> dict[str, Any]:
    """生成低风险 TodayActionDraft fallback。"""
    date = planning_input.today or "启动日"
    return {
        "title": "今日低强度启动行动草案",
        "date": date,
        "status": "draft_requires_confirmation",
        "actions": [
            {
                "name": "基线记录",
                "detail": "记录血压、静息心率、疲劳程度、颈肩不适和喘息程度；不训练也算完成。",
                "duration": "3-5分钟",
                "intensity": "无训练负荷",
            },
            {
                "name": "10分钟恢复流程",
                "detail": "下巴轻收、肩胛后收下沉、髋屈肌和小腿温和拉伸、轻松呼吸练习。",
                "duration": "约10分钟",
                "intensity": "RPE 1-2",
            },
            {
                "name": "可选轻松步行",
                "detail": "仅在血压和身体状态稳定时，轻松步行5-10分钟，保持能完整说话。",
                "duration": "5-10分钟",
                "intensity": "RPE 2-3",
            },
        ],
        "minimumCompletionStandard": "完成基线记录；如状态稳定，再做10分钟恢复流程。身体不稳时只记录也算完成。",
        "downgradeRule": "如疲劳、血压异常、颈肩不适或喘息明显，只做基线记录和呼吸恢复，不补量、不加练。",
        "stopConditions": [
            "胸闷、头晕、异常心悸或血压明显高于平时",
            "颈部放射痛、麻木、恶心、电击样感觉或症状加重",
            "游泳或呼吸练习中出现呛水、慌乱或明显呼吸不适",
            "任何动作疼痛达到4分以上",
        ],
        "feedbackFields": [
            "早晚血压",
            "静息心率",
            "颈肩不适评分",
            "喘息程度",
            "完成了哪些最低行动",
        ],
        "exclusions": [
            "不做 HIIT、Tabata、高强度间歇或极限冲刺。",
            "不做颈部负重、颈桥、颈后动作或憋气冲重量。",
            "不做长距离连续游泳，不硬凑25米，不冲1000米目标。",
        ],
    }


def _non_empty_list(value: Any) -> bool:
    """判断字段是否为非空 list。"""
    return isinstance(value, list) and bool(value)


def _missing_info_markers(text: str) -> set[str]:
    """从输出文本中识别模型自己声明的缺失信息。"""
    markers: set[str] = set()
    pairs = {
        "age": ("年龄未知", "未提供年龄", "unknown age", "age unknown"),
        "height": ("身高未知", "未提供身高", "unknown height", "height unknown"),
        "weight": ("体重未知", "未提供体重", "unknown weight", "weight unknown"),
        "medication": ("用药史未知", "未提供用药", "unknown medication"),
        "venue": ("场地未知", "未提供场地", "unknown venue"),
        "equipment": ("器械未知", "未提供器械", "unknown equipment"),
        "doctor_limit": ("医生限制未知", "未提供医生限制", "unknown doctor"),
    }
    lowered = text.lower()
    for marker, phrases in pairs.items():
        if any(phrase.lower() in lowered for phrase in phrases):
            markers.add(marker)
    return markers


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
