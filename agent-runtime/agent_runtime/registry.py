from __future__ import annotations

from typing import Any, Mapping, Protocol


class Skill(Protocol):
    trigger: str

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        ...


class SkillRegistry:
    """Registry for runtime skills keyed by trigger."""

    def __init__(self, skills: list[Skill] | None = None) -> None:
        self._skills: dict[str, Skill] = {}
        for skill in skills or []:
            self.register(skill)

    def register(self, skill: Skill) -> None:
        trigger = str(skill.trigger).strip().upper()
        if not trigger:
            raise ValueError("Skill trigger must not be empty")
        self._skills[trigger] = skill

    def get(self, trigger: str) -> Skill | None:
        return self._skills.get(str(trigger).strip().upper())

    def dispatch(self, trigger: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        skill = self.get(trigger)
        if skill is None:
            raise KeyError(f"Unsupported trigger: {trigger}")
        return skill.run(payload)

    @property
    def triggers(self) -> tuple[str, ...]:
        return tuple(sorted(self._skills))
