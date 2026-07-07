import os
import unittest
from unittest.mock import patch

from agent.models import (
    BaseModelProvider,
    OpenAICompatibleProvider,
    ProviderConfigurationError,
)
from agent.skills import InitialPlanningSkill


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

    def test_skill_debug_trace_defaults_to_off(self) -> None:
        with patch.dict(os.environ, {"REBOOT_HEALTH_AGENT_DEBUG_TRACE": ""}, clear=False):
            with patch("agent.skills.initial_planning.LOGGER.info") as info:
                InitialPlanningSkill().run(_sample_payload())

        info.assert_not_called()

    def test_skill_debug_trace_logs_phase_shapes_when_enabled(self) -> None:
        user_text = _sample_payload()["userText"]

        with patch.dict(os.environ, {"REBOOT_HEALTH_AGENT_DEBUG_TRACE": "true"}, clear=False):
            with self.assertLogs("agent.skills.initial_planning", level="INFO") as logs:
                InitialPlanningSkill().run(_sample_payload())

        serialized = "\n".join(logs.output)
        for event in (
            "skill_input_normalized",
            "skill_prompt_loaded",
            "skill_provider_output_received",
            "skill_output_mapped",
            "runtime_boundaries_applied",
            "skill_schema_validated",
            "skill_forbidden_claims_checked",
        ):
            self.assertIn(event, serialized)
        self.assertIn("fieldTypes", serialized)
        self.assertIn('"todayActionDraft": "dict"', serialized)
        self.assertIn("todayActionDraftSource", serialized)
        self.assertNotIn(user_text, serialized)

    def test_today_action_debug_source_is_provider_dict_complete(self) -> None:
        secret = "placeholder-not-a-real-api-key"
        skill = InitialPlanningSkill(
            provider=_StaticProvider(
                _planning_output(
                    today_action=_complete_today_action(),
                    summary=f"待确认草案，不应在日志输出 {secret}",
                )
            )
        )

        with patch.dict(
            os.environ,
            {
                "REBOOT_HEALTH_AGENT_DEBUG_TRACE": "true",
                "REBOOT_HEALTH_MODEL_API_KEY": secret,
            },
            clear=False,
        ):
            with self.assertLogs("agent.skills.initial_planning", level="INFO") as logs:
                result = skill.run(_sample_payload())

        serialized = "\n".join(logs.output)
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertIn("provider_dict_complete", serialized)
        self.assertIn('"todayActionDraftMissingFields": []', serialized)
        self.assertNotIn(secret, serialized)

    def test_today_action_debug_source_reports_missing_fields_completed_by_fallback(self) -> None:
        skill = InitialPlanningSkill(
            provider=_StaticProvider(
                _planning_output(
                    today_action={
                        "status": "draft_requires_confirmation",
                        "title": "今日行动草案",
                        "date": "2026-07-06",
                    }
                )
            )
        )

        with patch.dict(os.environ, {"REBOOT_HEALTH_AGENT_DEBUG_TRACE": "true"}, clear=False):
            with self.assertLogs("agent.skills.initial_planning", level="INFO") as logs:
                result = skill.run(_sample_payload())

        serialized = "\n".join(logs.output)
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertGreaterEqual(len(result["todayActionDraft"]["actions"]), 1)
        self.assertIn(
            "provider_dict_missing_required_fields_completed_by_fallback",
            serialized,
        )
        self.assertIn("todayActionDraftMissingFields", serialized)
        self.assertIn('"actions"', serialized)
        self.assertIn('"minimumCompletionStandard"', serialized)

    def test_today_action_debug_source_reports_invalid_replaced_by_fallback(self) -> None:
        invalid_values = ("today action as text", ["bad"], None)
        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                skill = InitialPlanningSkill(
                    provider=_StaticProvider(_planning_output(today_action=invalid_value))
                )

                with patch.dict(
                    os.environ,
                    {"REBOOT_HEALTH_AGENT_DEBUG_TRACE": "true"},
                    clear=False,
                ):
                    with self.assertLogs(
                        "agent.skills.initial_planning",
                        level="INFO",
                    ) as logs:
                        result = skill.run(_sample_payload())

                serialized = "\n".join(logs.output)
                self.assertTrue(result["requiresUserConfirmation"])
                self.assertIsInstance(result["todayActionDraft"], dict)
                self.assertIn("provider_invalid_replaced_by_fallback", serialized)
                self.assertIn("todayActionDraftMissingFields", serialized)

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


def _planning_output(today_action, summary: str = "生成待确认草案。") -> dict:
    return {
        "schemaVersion": "health-agent.initial-planning.v0",
        "summary": summary,
        "understandingCandidates": [{"type": "status", "text": "想恢复训练"}],
        "healthConstraintCandidates": [{"name": "低强度起步"}],
        "goalCandidates": [{"name": "恢复基础体能"}],
        "programDraft": {"status": "draft_requires_confirmation"},
        "phaseDraft": {"status": "draft_requires_confirmation"},
        "weeklyPlanDraft": {"status": "draft_requires_confirmation", "days": []},
        "todayActionDraft": today_action,
        "safetyNotes": ["需要确认后执行。"],
        "questions": [],
        "requiresUserConfirmation": False,
    }


def _complete_today_action() -> dict:
    return {
        "status": "draft_requires_confirmation",
        "title": "今日低强度启动行动草案",
        "date": "2026-07-06",
        "actions": [
            {
                "name": "基线记录",
                "detail": "记录血压、疲劳程度、颈肩不适和喘息程度。",
                "duration": "3-5分钟",
                "intensity": "无训练负荷",
            }
        ],
        "minimumCompletionStandard": "完成基线记录即可。",
        "downgradeRule": "如状态不稳，只做记录，不训练。",
        "stopConditions": ["胸闷、头晕或异常心悸时停止。"],
        "feedbackFields": ["血压", "颈肩不适评分", "喘息程度"],
        "exclusions": ["不做 HIIT、Tabata 或高强度间歇。"],
    }


class _StaticProvider(BaseModelProvider):
    provider_name = "fake-openai-compatible"

    def __init__(self, output: dict) -> None:
        self.output = output

    def generate_initial_planning(self, prompt, planning_input):
        return self.output


if __name__ == "__main__":
    unittest.main()
