import unittest

from agent_runtime.providers import OpenAICompatibleProvider, ProviderConfigurationError
from agent_runtime.skills import InitialPlanningSkill


FORBIDDEN_CLAIMS = (
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


class InitialPlanningSkillTest(unittest.TestCase):
    def test_mock_provider_generates_required_output_shape(self) -> None:
        skill = InitialPlanningSkill()

        result = skill.run(_sample_payload())

        self.assertEqual(result["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertTrue(result["requiresUserConfirmation"])
        for key in (
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
        ):
            self.assertIn(key, result)

    def test_initial_planning_contains_weekly_and_today_drafts(self) -> None:
        result = InitialPlanningSkill().run(_sample_payload())

        self.assertEqual(result["weeklyPlanDraft"]["status"], "draft_requires_confirmation")
        self.assertGreaterEqual(len(result["weeklyPlanDraft"]["days"]), 7)
        self.assertEqual(result["todayActionDraft"]["status"], "draft_requires_confirmation")
        self.assertGreaterEqual(len(result["todayActionDraft"]["actions"]), 3)

    def test_health_risks_are_handled_conservatively(self) -> None:
        result = InitialPlanningSkill().run(_sample_payload())
        text = _flatten(result)

        self.assertIn("颈椎", text)
        self.assertIn("呛水", text)
        self.assertIn("血压", text)
        self.assertIn("不硬游25米", text)
        self.assertIn("RPE 3-6", text)
        self.assertNotIn("HIIT训练", text)
        self.assertNotIn("Tabata训练", text)
        self.assertNotIn("1RM测试安排", text)

    def test_output_does_not_claim_business_fact_changes(self) -> None:
        result = InitialPlanningSkill().run(_sample_payload())
        text = _flatten(result)

        for phrase in FORBIDDEN_CLAIMS:
            self.assertNotIn(phrase, text)

    def test_openai_provider_requires_environment_configuration(self) -> None:
        with self.assertRaises(ProviderConfigurationError):
            OpenAICompatibleProvider(env={})


def _sample_payload() -> dict:
    return {
        "userText": "34岁，体重偏高，篮球两个回合就喘。颈椎不太好，游泳不会换气容易呛水，血压大概140/90，想减脂并恢复体能。",
        "profile": {
            "age": 34,
            "heightCm": 175,
            "weightKg": 94,
            "bloodPressure": "140/90",
            "medication": "每日降压药",
        },
        "knownHealthConstraints": [
            {"name": "多节段颈椎间盘突出"},
            {"name": "游泳呛水风险"},
        ],
        "goals": [
            {"name": "12周恢复规律训练"},
            {"name": "减脂到更健康体重"},
        ],
        "today": "2026-07-06",
    }


def _flatten(value) -> str:
    if isinstance(value, dict):
        return "\n".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten(item) for item in value)
    return str(value)


if __name__ == "__main__":
    unittest.main()
