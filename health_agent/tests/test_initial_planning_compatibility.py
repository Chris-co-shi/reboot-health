import json
import unittest

from agent.models import ModelResponse, ModelToolCall, ProviderResponseError
from agent.skills.initial_planning import InitialPlanningSkill

from tests.support.scripted_model_provider import ScriptedModelProvider


class InitialPlanningCompatibilityTest(unittest.TestCase):
    def test_initial_planning_uses_generic_model_response_content(self) -> None:
        provider = ScriptedModelProvider(
            [ModelResponse(content=json.dumps(_planning_output(), ensure_ascii=False))]
        )
        skill = InitialPlanningSkill(provider=provider)

        result = skill.run({"userText": "想恢复规律训练。"})

        self.assertEqual(result["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertEqual(result["todayActionDraft"]["status"], "draft_requires_confirmation")
        self.assertEqual(len(provider.calls), 1)
        messages = provider.calls[0]["messages"]
        self.assertEqual(messages[0].role, "system")
        self.assertEqual(messages[1].role, "user")
        self.assertIn("userText", messages[1].content)

    def test_initial_planning_rejects_tool_calls_in_compatibility_layer(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    content=None,
                    tool_calls=(
                        ModelToolCall(
                            id="call-1",
                            name="lookup",
                            raw_arguments="{}",
                            arguments={},
                        ),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )
        skill = InitialPlanningSkill(provider=provider)

        with self.assertRaises(ProviderResponseError) as context:
            skill.run({"userText": "查询一下历史记录。"})

        self.assertEqual(context.exception.code, "tool_calls_not_supported")

    def test_initial_planning_invalid_json_content_fails_clearly(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="not json")])
        skill = InitialPlanningSkill(provider=provider)

        with self.assertRaises(ProviderResponseError) as context:
            skill.run({"userText": "想训练"})

        self.assertEqual(context.exception.code, "invalid_json")

    def test_unknown_health_facts_are_not_injected_by_runtime_boundaries(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    content=json.dumps(_insufficient_output(), ensure_ascii=False)
                )
            ]
        )
        skill = InitialPlanningSkill(provider=provider)

        result = skill.run({"userText": "我想恢复训练，从低强度开始。"})

        flattened = json.dumps(result, ensure_ascii=False)
        for forbidden in (
            "颈椎",
            "血压",
            "游泳",
            "呛水",
            "心脏",
            "颈后下拉",
            "颈后推举",
        ):
            self.assertNotIn(forbidden, flattened)

    def test_insufficient_information_status_passes_without_filled_plan(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    content=json.dumps(_insufficient_output(), ensure_ascii=False)
                )
            ]
        )
        skill = InitialPlanningSkill(provider=provider)

        result = skill.run({"userText": "想恢复训练"})

        self.assertEqual(result["programDraft"]["status"], "insufficient_information")
        self.assertEqual(result["phaseDraft"]["status"], "insufficient_information")
        self.assertEqual(result["weeklyPlanDraft"]["days"], [])
        self.assertEqual(result["todayActionDraft"]["actions"], [])

    def test_missing_today_action_actions_are_not_completed_by_business_fallback(self) -> None:
        output = _insufficient_output()
        output["todayActionDraft"] = {"status": "insufficient_information"}
        provider = ScriptedModelProvider(
            [ModelResponse(content=json.dumps(output, ensure_ascii=False))]
        )
        skill = InitialPlanningSkill(provider=provider)

        result = skill.run({"userText": "想恢复训练"})

        self.assertEqual(result["todayActionDraft"]["actions"], [])
        flattened = json.dumps(result["todayActionDraft"], ensure_ascii=False)
        for forbidden in ("步行", "游泳", "骑行", "拉伸", "血压记录"):
            self.assertNotIn(forbidden, flattened)


def _planning_output() -> dict:
    return {
        "schemaVersion": "health-agent.initial-planning.v0",
        "summary": "生成待确认草案。",
        "understandingCandidates": [],
        "healthConstraintCandidates": [],
        "goalCandidates": [],
        "programDraft": {"status": "draft_requires_confirmation"},
        "phaseDraft": {"status": "draft_requires_confirmation"},
        "weeklyPlanDraft": {
            "status": "draft_requires_confirmation",
            "days": [],
        },
        "todayActionDraft": {
            "status": "draft_requires_confirmation",
            "title": "今日低强度行动草案",
            "actions": [{"name": "记录状态"}],
            "minimumCompletionStandard": "完成记录。",
            "downgradeRule": "状态不稳则只记录。",
            "stopConditions": ["胸闷或头晕时停止。"],
            "feedbackFields": ["疲劳程度"],
            "exclusions": ["不做高强度间歇。"],
        },
        "safetyNotes": [],
        "questions": [],
        "requiresUserConfirmation": True,
    }


def _insufficient_output() -> dict:
    return {
        "schemaVersion": "health-agent.initial-planning.v0",
        "summary": "信息不足，需要先确认偏好和目标。",
        "understandingCandidates": [],
        "healthConstraintCandidates": [],
        "goalCandidates": [],
        "programDraft": {"status": "insufficient_information"},
        "phaseDraft": {"status": "insufficient_information"},
        "weeklyPlanDraft": {"status": "insufficient_information", "days": []},
        "todayActionDraft": {"status": "insufficient_information", "actions": []},
        "safetyNotes": [],
        "questions": [
            {
                "field": "goals",
                "question": "您希望通过恢复训练实现什么目标？",
            }
        ],
        "requiresUserConfirmation": True,
    }


if __name__ == "__main__":
    unittest.main()
