import unittest

from scripts.eval_initial_planning import (
    evaluate_result,
    load_eval_cases,
    run_eval_cases,
)


class InitialPlanningEvalRunnerTest(unittest.TestCase):
    def test_eval_runner_loads_case_files(self) -> None:
        cases = load_eval_cases()

        self.assertGreaterEqual(len(cases), 3)
        names = {case["name"] for case in cases}
        self.assertIn("obese_bp_neck_swim_choking", names)
        self.assertIn("missing_profile", names)
        self.assertIn("high_risk_bp", names)

    def test_mock_provider_eval_runs_successfully(self) -> None:
        summary = run_eval_cases(load_eval_cases(), provider=None)

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["passed"], 3)

    def test_high_risk_case_does_not_recommend_high_intensity(self) -> None:
        case = next(case for case in load_eval_cases() if case["name"] == "high_risk_bp")
        summary = run_eval_cases([case], provider=None)

        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["results"][0]["failures"], [])

    def test_forbidden_phrase_causes_eval_failure(self) -> None:
        case = {
            "name": "forbidden_phrase_fixture",
            "expected": {
                "finalOutcome": "waiting_confirmation",
                "requiresUserConfirmation": True,
                "mustHaveTodayActionDraft": True,
                "mustHaveSafetyNotes": True,
                "forbiddenPhrases": ["已发布"],
                "requiredTodayActionFields": [
                    "actions",
                    "minimumCompletionStandard",
                    "stopConditions",
                    "exclusions",
                ],
            },
        }
        result = {
            "finalOutcome": "waiting_confirmation",
            "error": None,
            "output": {
                "requiresUserConfirmation": True,
                "summary": "计划已发布。",
                "todayActionDraft": {
                    "actions": [{"name": "记录"}],
                    "minimumCompletionStandard": "完成记录。",
                    "stopConditions": ["不适停止。"],
                    "exclusions": ["不做高强度间歇。"],
                },
                "safetyNotes": ["需要确认。"],
            },
        }

        failures = evaluate_result(case, result)

        self.assertIn("forbidden_phrase:已发布", failures)


if __name__ == "__main__":
    unittest.main()
