import unittest

from agent.schemas.planning import (
    PlanningOutput,
    SchemaValidationError,
    validate_planning_output,
)


class PlanningSchemaTest(unittest.TestCase):
    def test_questions_must_be_structured_objects(self) -> None:
        output = PlanningOutput.from_mapping(
            {
                **_base_output(),
                "questions": [
                    {
                        "field": "goals",
                        "question": "您的主要目标是什么？",
                    }
                ],
            }
        ).to_dict()

        self.assertEqual(output["questions"][0]["field"], "goals")
        self.assertEqual(output["questions"][0]["question"], "您的主要目标是什么？")
        validate_planning_output(output)

    def test_question_string_is_rejected(self) -> None:
        with self.assertRaises(SchemaValidationError) as context:
            PlanningOutput.from_mapping(
                {
                    **_base_output(),
                    "questions": [
                        "{'field': 'goals', 'question': '您的主要目标是什么？'}"
                    ],
                }
            )

        self.assertIn("questions[0] must be an object, got string", str(context.exception))

    def test_insufficient_information_drafts_allow_empty_days_and_actions(self) -> None:
        output = {
            **_base_output(),
            "programDraft": {"status": "insufficient_information"},
            "phaseDraft": {"status": "insufficient_information"},
            "weeklyPlanDraft": {"status": "insufficient_information", "days": []},
            "todayActionDraft": {"status": "insufficient_information", "actions": []},
        }

        validated = validate_planning_output(output)

        self.assertEqual(validated["programDraft"]["status"], "insufficient_information")
        self.assertEqual(validated["weeklyPlanDraft"]["days"], [])
        self.assertEqual(validated["todayActionDraft"]["actions"], [])


def _base_output() -> dict:
    return {
        "schemaVersion": "health-agent.initial-planning.v0",
        "summary": "生成待确认草案。",
        "understandingCandidates": [],
        "healthConstraintCandidates": [],
        "goalCandidates": [],
        "programDraft": {"status": "draft_requires_confirmation"},
        "phaseDraft": {"status": "draft_requires_confirmation"},
        "weeklyPlanDraft": {"status": "draft_requires_confirmation", "days": []},
        "todayActionDraft": {"status": "draft_requires_confirmation", "actions": []},
        "safetyNotes": [],
        "questions": [],
        "requiresUserConfirmation": True,
    }


if __name__ == "__main__":
    unittest.main()
