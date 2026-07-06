from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


PLANNING_SCHEMA_VERSION = "health-agent.initial-planning.v0"

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
class PlanningInput:
    userText: str
    profile: dict[str, Any] = field(default_factory=dict)
    knownHealthConstraints: list[Any] = field(default_factory=list)
    goals: list[Any] = field(default_factory=list)
    recentRecords: list[Any] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    today: str | None = None
    locale: str = "zh-CN"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PlanningInput":
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
        )

    def to_provider_payload(self) -> dict[str, Any]:
        return {
            "userText": self.userText,
            "profile": self.profile,
            "knownHealthConstraints": self.knownHealthConstraints,
            "goals": self.goals,
            "recentRecords": self.recentRecords,
            "preferences": self.preferences,
            "today": self.today,
            "locale": self.locale,
        }


@dataclass
class PlanningOutput:
    summary: str
    understandingCandidates: list[dict[str, Any]] = field(default_factory=list)
    healthConstraintCandidates: list[dict[str, Any]] = field(default_factory=list)
    goalCandidates: list[dict[str, Any]] = field(default_factory=list)
    programDraft: dict[str, Any] = field(default_factory=dict)
    phaseDraft: dict[str, Any] = field(default_factory=dict)
    weeklyPlanDraft: dict[str, Any] = field(default_factory=dict)
    todayActionDraft: dict[str, Any] = field(default_factory=dict)
    safetyNotes: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    requiresUserConfirmation: bool = True
    schemaVersion: str = PLANNING_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "PlanningOutput":
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
            questions=[str(item) for item in _as_list(data.get("questions"))],
            requiresUserConfirmation=bool(
                data.get("requiresUserConfirmation", True)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
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
            "questions": self.questions,
            "requiresUserConfirmation": self.requiresUserConfirmation,
        }


def validate_planning_output(value: Mapping[str, Any]) -> dict[str, Any]:
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
        "questions",
    ):
        if not isinstance(data[key], list):
            raise SchemaValidationError(f"Planning output field must be a list: {key}")

    for key in ("programDraft", "phaseDraft", "weeklyPlanDraft", "todayActionDraft"):
        if not isinstance(data[key], dict):
            raise SchemaValidationError(f"Planning output field must be an object: {key}")

    return data


def _first_present(data: Mapping[str, Any], *keys: str, default: Any) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_list_of_mappings(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(value):
        if isinstance(item, Mapping):
            result.append(dict(item))
        else:
            result.append({"text": str(item), "candidate": True})
    return result


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
