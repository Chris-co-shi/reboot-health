"""INITIAL_PLANNING v0 的输入输出 Schema 与轻量校验。

这里的对象是 Python Agent 与 Provider/Skill 之间的稳定边界。它们只描述候选、
草案和需要确认的信息，不代表已经写入已确认健康事实。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


# 当前单技能输出合同版本。修改字段时必须同步更新测试和调用方合同。
PLANNING_SCHEMA_VERSION = "health-agent.initial-planning.v0"
DRAFT_STATUS_DRAFT_REQUIRES_CONFIRMATION = "draft_requires_confirmation"
DRAFT_STATUS_INSUFFICIENT_INFORMATION = "insufficient_information"
ALLOWED_DRAFT_STATUSES = (
    DRAFT_STATUS_DRAFT_REQUIRES_CONFIRMATION,
    DRAFT_STATUS_INSUFFICIENT_INFORMATION,
)

# Provider 返回的 INITIAL_PLANNING 结果必须包含这些顶层字段。
REQUIRED_PLANNING_OUTPUT_KEYS = (
    "schemaVersion",
    "summary",
    "understandingCandidates",
    "healthConstraintCandidates",
    "goalCandidates",
    "programDraft",
    "phaseDraft",
    "weeklyPlanDraft",
    "todayActionDraft",
    "safetyNotes",
    "questions",
    "requiresUserConfirmation",
)


class SchemaValidationError(ValueError):
    """Raised when agent input or output does not match the v0 schema."""


@dataclass(frozen=True)
class PlanningQuestion:
    """模型需要向用户追问的结构化问题。"""

    field: str
    question: str
    reason: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], index: int) -> "PlanningQuestion":
        """从 JSON object 构建问题对象。"""
        field_value = str(value.get("field") or "").strip()
        question_value = str(value.get("question") or "").strip()
        reason_value = _optional_string(value.get("reason"))
        if not field_value:
            raise SchemaValidationError(f"questions[{index}].field must be a non-empty string")
        if not question_value:
            raise SchemaValidationError(
                f"questions[{index}].question must be a non-empty string"
            )
        return cls(field=field_value, question=question_value, reason=reason_value)

    def to_dict(self) -> dict[str, Any]:
        """返回 JSON-serializable dict。"""
        data: dict[str, Any] = {
            "field": self.field,
            "question": self.question,
        }
        if self.reason:
            data["reason"] = self.reason
        return data


@dataclass(frozen=True)
class PlanningInput:
    """INITIAL_PLANNING Skill 的规范化输入。

    上游可以传入多种历史字段名，本类负责归一化成 Provider 能稳定消费的形状。
    输入仍只是上下文，不等同于已确认健康事实。
    """

    userText: str
    profile: dict[str, Any] = field(default_factory=dict)
    knownHealthConstraints: list[Any] = field(default_factory=list)
    goals: list[Any] = field(default_factory=list)
    recentRecords: list[Any] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    today: str | None = None
    locale: str = "zh-CN"
    runtimeEnvironment: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PlanningInput":
        """从宽松字典创建规范输入，兼容旧字段名并过滤非预期类型。"""
        data = dict(value or {})
        return cls(
            userText=str(
                _first_present(
                    data,
                    "userText",
                    "user_text",
                    "userMessage",
                    "message",
                    "naturalLanguageStatus",
                    "healthStatus",
                    default="",
                )
            ).strip(),
            profile=_as_mapping(
                _first_present(data, "profile", "knownProfile", "userProfile", default={})
            ),
            knownHealthConstraints=_as_list(
                _first_present(
                    data,
                    "knownHealthConstraints",
                    "healthConstraints",
                    "constraints",
                    default=[],
                )
            ),
            goals=_as_list(
                _first_present(data, "goals", "knownGoals", "targetGoals", default=[])
            ),
            recentRecords=_as_list(
                _first_present(data, "recentRecords", "records", default=[])
            ),
            preferences=_as_mapping(
                _first_present(data, "preferences", "userPreferences", default={})
            ),
            today=_optional_string(_first_present(data, "today", "date", default=None)),
            locale=str(data.get("locale") or "zh-CN"),
            runtimeEnvironment=_as_mapping(data.get("runtimeEnvironment")),
        )

    def to_provider_payload(self) -> dict[str, Any]:
        """转成传给模型 Provider 的 JSON-like payload。"""
        return {
            "userText": self.userText,
            "profile": self.profile,
            "knownHealthConstraints": self.knownHealthConstraints,
            "goals": self.goals,
            "recentRecords": self.recentRecords,
            "preferences": self.preferences,
            "today": self.today,
            "locale": self.locale,
            "runtimeEnvironment": self.runtimeEnvironment,
        }


@dataclass
class PlanningOutput:
    """INITIAL_PLANNING Skill 的规范化输出。

    所有字段都是候选或草案。`requiresUserConfirmation` 在当前阶段必须为 True，
    用来保护重要健康事实、目标和计划发布不被 AI 自动确认。
    """

    summary: str
    understandingCandidates: list[dict[str, Any]] = field(default_factory=list)
    healthConstraintCandidates: list[dict[str, Any]] = field(default_factory=list)
    goalCandidates: list[dict[str, Any]] = field(default_factory=list)
    programDraft: dict[str, Any] = field(default_factory=dict)
    phaseDraft: dict[str, Any] = field(default_factory=dict)
    weeklyPlanDraft: dict[str, Any] = field(default_factory=dict)
    todayActionDraft: dict[str, Any] = field(default_factory=dict)
    safetyNotes: list[str] = field(default_factory=list)
    questions: tuple[PlanningQuestion, ...] = ()
    requiresUserConfirmation: bool = True
    schemaVersion: str = PLANNING_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PlanningOutput":
        """从 Provider 返回值构造规范输出，并为缺失字段提供保守默认值。"""
        data = dict(value or {})
        return cls(
            schemaVersion=str(data.get("schemaVersion") or PLANNING_SCHEMA_VERSION),
            summary=str(
                data.get("summary")
                or "已生成一份待确认的 INITIAL_PLANNING 草案。"
            ),
            understandingCandidates=_as_list_of_mappings(
                data.get("understandingCandidates")
            ),
            healthConstraintCandidates=_as_list_of_mappings(
                data.get("healthConstraintCandidates")
            ),
            goalCandidates=_as_list_of_mappings(data.get("goalCandidates")),
            programDraft=_as_mapping(data.get("programDraft")),
            phaseDraft=_as_mapping(data.get("phaseDraft")),
            weeklyPlanDraft=_as_mapping(data.get("weeklyPlanDraft")),
            todayActionDraft=_as_mapping(data.get("todayActionDraft")),
            safetyNotes=[str(item) for item in _as_list(data.get("safetyNotes"))],
            questions=_as_questions(data.get("questions")),
            requiresUserConfirmation=bool(
                data.get("requiresUserConfirmation", True)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """返回可序列化、可被校验和测试断言的输出字典。"""
        return {
            "schemaVersion": self.schemaVersion,
            "summary": self.summary,
            "understandingCandidates": self.understandingCandidates,
            "healthConstraintCandidates": self.healthConstraintCandidates,
            "goalCandidates": self.goalCandidates,
            "programDraft": self.programDraft,
            "phaseDraft": self.phaseDraft,
            "weeklyPlanDraft": self.weeklyPlanDraft,
            "todayActionDraft": self.todayActionDraft,
            "safetyNotes": self.safetyNotes,
            "questions": [question.to_dict() for question in self.questions],
            "requiresUserConfirmation": self.requiresUserConfirmation,
        }


def validate_planning_output(value: Mapping[str, Any]) -> dict[str, Any]:
    """校验 INITIAL_PLANNING 输出合同。

    本函数只做结构和关键安全边界校验：字段完整、版本匹配、必须等待用户确认，
    以及候选/草案字段类型正确。
    """
    data = dict(value)
    missing = [key for key in REQUIRED_PLANNING_OUTPUT_KEYS if key not in data]
    if missing:
        raise SchemaValidationError(f"Planning output missing keys: {', '.join(missing)}")
    if data["schemaVersion"] != PLANNING_SCHEMA_VERSION:
        raise SchemaValidationError(
            f"Unsupported planning schemaVersion: {data['schemaVersion']}"
        )
    if data["requiresUserConfirmation"] is not True:
        raise SchemaValidationError(
            "Initial planning output must require user confirmation"
        )

    for key in (
        "understandingCandidates",
        "healthConstraintCandidates",
        "goalCandidates",
        "safetyNotes",
    ):
        if not isinstance(data[key], list):
            raise SchemaValidationError(f"Planning output field must be a list: {key}")

    if not isinstance(data["questions"], list):
        raise SchemaValidationError("Planning output field must be a list: questions")
    for index, question in enumerate(data["questions"]):
        if not isinstance(question, Mapping):
            type_name = "string" if isinstance(question, str) else type(question).__name__
            raise SchemaValidationError(
                f"questions[{index}] must be an object, got {type_name}"
            )
        PlanningQuestion.from_mapping(question, index)

    for key in ("programDraft", "phaseDraft", "weeklyPlanDraft", "todayActionDraft"):
        if not isinstance(data[key], dict):
            raise SchemaValidationError(f"Planning output field must be an object: {key}")
        status = data[key].get("status")
        if status not in ALLOWED_DRAFT_STATUSES:
            raise SchemaValidationError(
                f"{key}.status must be draft_requires_confirmation or insufficient_information"
            )

    weekly_days = data["weeklyPlanDraft"].get("days")
    if weekly_days is not None and not isinstance(weekly_days, list):
        raise SchemaValidationError("weeklyPlanDraft.days must be a list")

    today_actions = data["todayActionDraft"].get("actions")
    if today_actions is not None and not isinstance(today_actions, list):
        raise SchemaValidationError("todayActionDraft.actions must be a list")

    return data


def _first_present(data: Mapping[str, Any], *keys: str, default: Any) -> Any:
    """按顺序读取第一个存在且非 None 的字段，用于兼容历史输入命名。"""
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _as_mapping(value: Any) -> dict[str, Any]:
    """把 Mapping 安全复制为 dict，其他类型按空对象处理。"""
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list[Any]:
    """把可接受的单值、tuple 或 list 统一成 list。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_list_of_mappings(value: Any) -> list[dict[str, Any]]:
    """把 Provider 输出统一成对象列表，字符串等简单值降级为候选文本。"""
    result: list[dict[str, Any]] = []
    for item in _as_list(value):
        if isinstance(item, Mapping):
            result.append(dict(item))
        else:
            result.append({"text": str(item), "candidate": True})
    return result


def _as_questions(value: Any) -> tuple[PlanningQuestion, ...]:
    """把 Provider 输出校验为结构化问题数组。"""
    result: list[PlanningQuestion] = []
    for index, item in enumerate(_as_list(value)):
        if not isinstance(item, Mapping):
            type_name = "string" if isinstance(item, str) else type(item).__name__
            raise SchemaValidationError(
                f"questions[{index}] must be an object, got {type_name}"
            )
        result.append(PlanningQuestion.from_mapping(item, index))
    return tuple(result)


def _optional_string(value: Any) -> str | None:
    """把可选字段规范化成去空白字符串；空值返回 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
