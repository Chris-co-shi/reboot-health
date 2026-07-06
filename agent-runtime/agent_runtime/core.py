from __future__ import annotations

from typing import Any, Mapping

from agent_runtime.providers.base import ProviderResponseError
from agent_runtime.providers.mock import MockProvider
from agent_runtime.registry import SkillRegistry
from agent_runtime.schema import SchemaValidationError
from agent_runtime.skills.initial_planning import InitialPlanningSkill


AGENT_CORE_SCHEMA_VERSION = "health-agent.core.v0"


class AgentCore:
    """Thin trigger dispatcher for Python Health Agent skills."""

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry()

    @classmethod
    def default(cls, provider: Any | None = None) -> "AgentCore":
        registry = SkillRegistry()
        registry.register(InitialPlanningSkill(provider=provider or MockProvider()))
        return cls(registry=registry)

    def run(
        self,
        trigger_or_request: str | Mapping[str, Any],
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        trigger, skill_payload = self._normalize_request(trigger_or_request, payload)
        skill = self.registry.get(trigger)
        if skill is None:
            return self._unsupported(trigger)

        try:
            return skill.run(skill_payload)
        except (ProviderResponseError, SchemaValidationError, ValueError) as exc:
            return {
                "schemaVersion": AGENT_CORE_SCHEMA_VERSION,
                "trigger": trigger,
                "status": "error",
                "error": {
                    "code": "SKILL_FAILED",
                    "message": str(exc),
                },
                "requiresUserConfirmation": False,
            }

    def _normalize_request(
        self,
        trigger_or_request: str | Mapping[str, Any],
        payload: Mapping[str, Any] | None,
    ) -> tuple[str, Mapping[str, Any]]:
        if isinstance(trigger_or_request, str):
            return trigger_or_request.strip().upper(), payload or {}

        request = dict(trigger_or_request)
        trigger = str(
            request.get("trigger")
            or request.get("type")
            or request.get("intent")
            or ""
        ).strip().upper()
        skill_payload = request.get("input")
        if skill_payload is None:
            skill_payload = request.get("payload")
        if skill_payload is None:
            skill_payload = request.get("data")
        if skill_payload is None:
            skill_payload = {}
        if not isinstance(skill_payload, Mapping):
            raise ValueError("AgentCore request input must be an object")
        return trigger, skill_payload

    def _unsupported(self, trigger: str) -> dict[str, Any]:
        return {
            "schemaVersion": AGENT_CORE_SCHEMA_VERSION,
            "trigger": trigger or "UNKNOWN",
            "status": "unsupported",
            "error": {
                "code": "UNSUPPORTED_TRIGGER",
                "message": f"Unsupported trigger: {trigger or 'UNKNOWN'}",
            },
            "requiresUserConfirmation": False,
        }
