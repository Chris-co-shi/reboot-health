import json
import os
import unittest
from unittest.mock import patch

from scripts.smoke_initial_planning import (
    _redacted_draft_summary,
    _redacted_summary,
)


FULL_USER_TEXT = "体能差，游泳容易呛水，血压有点高，想从低强度恢复训练。"


class SmokeInitialPlanningSummaryTest(unittest.TestCase):
    def test_smoke_default_summary_does_not_include_draft_details(self) -> None:
        summary = _redacted_summary(_agent_run_result())
        serialized = json.dumps(summary, ensure_ascii=False)

        self.assertNotIn("programDraft", summary)
        self.assertNotIn("phaseDraft", summary)
        self.assertNotIn("weeklyPlanDraft", summary)
        self.assertNotIn("todayActionDraft", summary)
        self.assertNotIn(FULL_USER_TEXT, serialized)

    def test_smoke_print_draft_summary_includes_draft_sections(self) -> None:
        summary = _redacted_draft_summary(
            _agent_run_result(),
            source_payload={"userText": FULL_USER_TEXT},
        )

        for key in (
            "programDraft",
            "phaseDraft",
            "weeklyPlanDraft",
            "todayActionDraft",
            "safetyNotes",
            "questions",
            "memoryCandidatesPreview",
            "warnings",
            "qualityWarningCount",
            "error",
        ):
            self.assertIn(key, summary)

    def test_smoke_print_draft_summary_does_not_include_api_key(self) -> None:
        api_key = "placeholder-not-a-real-api-key"
        result = _agent_run_result(secret_text=api_key)

        with patch.dict(os.environ, {"REBOOT_HEALTH_MODEL_API_KEY": api_key}):
            summary = _redacted_draft_summary(
                result,
                source_payload={"userText": FULL_USER_TEXT},
            )

        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn(api_key, serialized)
        self.assertIn("<redacted>", serialized)

    def test_smoke_print_draft_summary_does_not_include_full_user_text(self) -> None:
        result = _agent_run_result(include_user_text=True)

        summary = _redacted_draft_summary(
            result,
            source_payload={"userText": FULL_USER_TEXT},
        )

        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn(FULL_USER_TEXT, serialized)
        self.assertIn("<redacted-health-input>", serialized)

    def test_smoke_print_draft_summary_includes_quality_warning_count(self) -> None:
        summary = _redacted_draft_summary(
            _agent_run_result(
                warnings=[
                    "quality:warning:hiit_for_low_fitness:基础体能很低时不建议 HIIT。",
                    "provider warning",
                ]
            ),
            source_payload={"userText": FULL_USER_TEXT},
        )

        self.assertEqual(summary["warningCount"], 2)
        self.assertEqual(summary["qualityWarningCount"], 1)


def _agent_run_result(
    include_user_text: bool = False,
    secret_text: str | None = None,
    warnings: list[str] | None = None,
) -> dict:
    sensitive_detail = []
    if include_user_text:
        sensitive_detail.append(FULL_USER_TEXT)
    if secret_text:
        sensitive_detail.append(f"Bearer {secret_text}")
    detail = "；".join(sensitive_detail) or "低强度起步，等待用户确认。"
    return {
        "schemaVersion": "health-agent.run.v0",
        "runId": "run-test",
        "sessionId": "session-test",
        "status": "waiting_confirmation",
        "selectedSkill": "INITIAL_PLANNING",
        "finalOutcome": "waiting_confirmation",
        "trace": {
            "provider": "mock",
            "steps": [{"name": "context_built", "input": FULL_USER_TEXT}],
        },
        "output": {
            "schemaVersion": "health-agent.initial-planning.v0",
            "requiresUserConfirmation": True,
            "programDraft": {
                "status": "draft_requires_confirmation",
                "principles": ["低强度", "循序渐进", detail],
            },
            "phaseDraft": {
                "status": "draft_requires_confirmation",
                "focus": ["恢复节奏", "呼吸适应"],
            },
            "weeklyPlanDraft": {
                "status": "draft_requires_confirmation",
                "focus": "首周低强度适应。",
                "downgradePlan": "不适则停止或降级。",
            },
            "todayActionDraft": {
                "status": "draft_requires_confirmation",
                "minimumCompletionStandard": "最低完成：基线记录。",
            },
            "safetyNotes": ["需要确认后执行。"],
            "questions": ["是否有胸闷、头晕或异常心悸？"],
        },
        "memoryCandidates": [
            {
                "kind": "understanding",
                "content": FULL_USER_TEXT if include_user_text else "低强度恢复训练",
                "confidence": 0.7,
                "requiresUserConfirmation": True,
            }
        ],
        "warnings": warnings or [],
        "error": None,
    }


if __name__ == "__main__":
    unittest.main()
