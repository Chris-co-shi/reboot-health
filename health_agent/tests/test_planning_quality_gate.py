import unittest

from agent.models.base import BaseModelProvider
from agent.runtime.core import AgentCore
from agent.safety.planning_quality import PlanningQualityGate
from agent.skills.initial_planning import InitialPlanningSkill
from scripts.smoke_initial_planning import _redacted_summary


class PlanningQualityGateTest(unittest.TestCase):
    def test_quality_gate_rejects_auto_confirmed_output(self) -> None:
        result = PlanningQualityGate().evaluate(
            {"userText": "想恢复训练。"},
            _planning_output(requires_confirmation=False),
        )

        self.assertFalse(result.passed)
        self.assertIn("auto_confirmed_output", _codes(result))

    def test_quality_gate_warns_aggressive_swimming_for_choking_risk(self) -> None:
        output = _planning_output(
            weekly_plan={
                "status": "draft_requires_confirmation",
                "focus": "首周适应与恢复，但安排高强度游泳，连续游1000米。",
                "downgradePlan": "如呛水、头晕或胸闷则停止并降级。",
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "游泳不会换气，容易呛水。"},
            output,
        )

        self.assertIn("aggressive_swimming_for_choking_risk", _codes(result))

    def test_quality_gate_warns_hiit_for_low_fitness(self) -> None:
        output = _planning_output(
            weekly_plan={
                "status": "draft_requires_confirmation",
                "focus": "首周适应与恢复，但安排 HIIT、Tabata 和高强度间歇。",
                "downgradePlan": "如喘不过气、头晕或胸闷则停止并降级。",
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "体能差，篮球两个回合就喘。"},
            output,
        )

        self.assertIn("hiit_for_low_fitness", _codes(result))

    def test_quality_gate_does_not_warn_when_hiit_is_excluded(self) -> None:
        output = _planning_output(
            today_action={
                "title": "今日低强度行动草案",
                "status": "draft_requires_confirmation",
                "actions": [{"name": "基线记录", "detail": "记录血压和不适评分。"}],
                "minimumCompletionStandard": "最低完成：基线记录。",
                "downgradeRule": "不适则只记录。",
                "stopConditions": ["胸闷、头晕或想做 HIIT 时停止并降级。"],
                "feedbackFields": ["血压", "不适评分"],
                "exclusions": ["HIIT", "Tabata", "高强度间歇", "极限冲刺"],
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "体能差，篮球两个回合就喘。"},
            output,
        )

        self.assertNotIn("hiit_for_low_fitness", _codes(result))
        self.assertNotIn("today_action_too_large", _codes(result))

    def test_quality_gate_warns_when_hiit_is_recommended(self) -> None:
        output = _planning_output(
            weekly_plan={
                "status": "draft_requires_confirmation",
                "focus": "首周安排 HIIT 和 Tabata 作为主要训练。",
                "downgradePlan": "如喘不过气、头晕或胸闷则停止并降级。",
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "体能差，篮球两个回合就喘。"},
            output,
        )

        self.assertIn("hiit_for_low_fitness", _codes(result))

    def test_quality_gate_warns_heavy_neck_loading_for_cervical_issue(self) -> None:
        output = _planning_output(
            weekly_plan={
                "status": "draft_requires_confirmation",
                "focus": "首周适应与恢复，但安排颈桥、颈部负重和头倒立。",
                "downgradePlan": "如疼痛、头晕或麻木则停止并降级。",
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "颈椎不舒服，脖子容易紧。"},
            output,
        )

        self.assertIn("heavy_neck_loading_for_cervical_issue", _codes(result))

    def test_quality_gate_does_not_warn_when_long_swim_is_forbidden(self) -> None:
        output = _planning_output(
            today_action={
                "title": "今日低强度行动草案",
                "status": "draft_requires_confirmation",
                "actions": [{"name": "水中呼气", "detail": "只做扶池边呼气练习。"}],
                "minimumCompletionStandard": "最低完成：基线记录。",
                "downgradeRule": "呛水则停止。",
                "stopConditions": ["禁止连续游 1000 米；出现呛水立即停止。"],
                "feedbackFields": ["呛水次数", "慌乱程度"],
                "exclusions": ["连续游 1000 米", "高强度游泳"],
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "游泳 25 米都会呛水。"},
            output,
        )

        self.assertNotIn("aggressive_swimming_for_choking_risk", _codes(result))

    def test_quality_gate_warns_when_long_swim_is_recommended(self) -> None:
        output = _planning_output(
            weekly_plan={
                "status": "draft_requires_confirmation",
                "focus": "首周安排高强度游泳，并计划连续游 1000 米。",
                "downgradePlan": "如呛水、头晕或胸闷则停止并降级。",
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "游泳 25 米都会呛水。"},
            output,
        )

        self.assertIn("aggressive_swimming_for_choking_risk", _codes(result))

    def test_quality_gate_warns_high_intensity_for_blood_pressure_risk(self) -> None:
        output = _planning_output(
            weekly_plan={
                "status": "draft_requires_confirmation",
                "focus": "首周适应与恢复，但安排 1RM、极限力量、憋气和冲强度。",
                "downgradePlan": "如血压异常、胸闷或头晕则停止并降级。",
            }
        )

        result = PlanningQualityGate().evaluate(
            {"userText": "血压有点高，大概 140/90。"},
            output,
        )

        self.assertIn("high_intensity_for_blood_pressure_risk", _codes(result))

    def test_quality_gate_accepts_conservative_initial_plan(self) -> None:
        output = InitialPlanningSkill().run(
            {
                "userText": "34岁，体能差，篮球两个回合就喘。颈椎不太好，游泳不会换气容易呛水，血压大概140/90，想低强度恢复训练。",
                "profile": {"age": 34, "bloodPressure": "140/90"},
                "knownHealthConstraints": [
                    {"name": "颈椎间盘突出"},
                    {"name": "游泳呛水风险"},
                ],
            }
        )

        result = PlanningQualityGate().evaluate(
            {
                "userText": "34岁，体能差，篮球两个回合就喘。颈椎不太好，游泳不会换气容易呛水，血压大概140/90，想低强度恢复训练。",
                "profile": {"age": 34, "bloodPressure": "140/90"},
                "knownHealthConstraints": [
                    {"name": "颈椎间盘突出"},
                    {"name": "游泳呛水风险"},
                ],
            },
            output,
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.findings, ())

    def test_agent_loop_adds_quality_warning_to_agent_run_result(self) -> None:
        result = AgentCore.default(
            provider=_FakeProvider(
                _planning_output(
                    weekly_plan={
                        "status": "draft_requires_confirmation",
                        "focus": "首周适应与恢复，但安排 HIIT 和高强度间歇。",
                        "downgradePlan": "如喘不过气、头晕或胸闷则停止并降级。",
                    }
                )
            )
        ).run_detailed(
            "INITIAL_PLANNING",
            {"userText": "体能差，篮球两个回合就喘。"},
        )

        self.assertIn(
            "quality:warning:hiit_for_low_fitness",
            "\n".join(result.warnings),
        )
        self.assertTrue(
            any(step["name"] == "quality_gate_checked" for step in result.trace.steps)
        )

    def test_agent_run_result_contains_quality_warnings(self) -> None:
        result = AgentCore.default(
            provider=_FakeProvider(
                _planning_output(
                    weekly_plan={
                        "status": "draft_requires_confirmation",
                        "focus": "首周适应与恢复，但安排 HIIT 和高强度间歇。",
                        "downgradePlan": "如喘不过气、头晕或胸闷则停止并降级。",
                    }
                )
            )
        ).run_detailed(
            "INITIAL_PLANNING",
            {"userText": "体能差，篮球两个回合就喘。"},
        )

        payload = result.to_dict()
        self.assertIn("warnings", payload)
        self.assertIn(
            "quality:warning:hiit_for_low_fitness",
            "\n".join(payload["warnings"]),
        )
        self.assertIn(
            "quality:warning:hiit_for_low_fitness",
            "\n".join(payload["trace"]["warnings"]),
        )

    def test_agent_loop_adds_quality_warning_for_aggressive_plan(self) -> None:
        result = AgentCore.default(
            provider=_FakeProvider(
                _planning_output(
                    weekly_plan={
                        "status": "draft_requires_confirmation",
                        "focus": "首周适应与恢复，但安排连续游 1000 米和高强度游泳。",
                        "downgradePlan": "如呛水、头晕或胸闷则停止并降级。",
                    }
                )
            )
        ).run_detailed(
            "INITIAL_PLANNING",
            {"userText": "游泳 25 米都会呛水，想快速提高。"},
        )

        self.assertIn(
            "quality:warning:aggressive_swimming_for_choking_risk",
            "\n".join(result.warnings),
        )
        quality_steps = [
            step for step in result.trace.steps if step["name"] == "quality_gate_checked"
        ]
        self.assertEqual(quality_steps[-1]["qualityWarningCount"], 1)

    def test_agent_loop_keeps_conservative_plan_warning_free(self) -> None:
        result = AgentCore.default(
            provider=_FakeProvider(_planning_output())
        ).run_detailed(
            "INITIAL_PLANNING",
            {"userText": "想低强度恢复训练。"},
        )

        self.assertEqual(result.warnings, ())
        quality_steps = [
            step for step in result.trace.steps if step["name"] == "quality_gate_checked"
        ]
        self.assertEqual(quality_steps[-1]["qualityWarningCount"], 0)
        self.assertEqual(quality_steps[-1]["qualityErrorCount"], 0)

    def test_smoke_summary_contains_quality_warning_count(self) -> None:
        summary = _redacted_summary(
            {
                "schemaVersion": "health-agent.run.v0",
                "runId": "run-test",
                "sessionId": "session-test",
                "status": "waiting_confirmation",
                "selectedSkill": "INITIAL_PLANNING",
                "finalOutcome": "waiting_confirmation",
                "trace": {"provider": "mock"},
                "output": _planning_output(),
                "memoryCandidates": [],
                "warnings": [
                    "quality:warning:hiit_for_low_fitness:基础体能很低时不建议 HIIT。",
                    "provider warning",
                ],
                "error": None,
            }
        )

        self.assertEqual(summary["warningCount"], 2)
        self.assertEqual(summary["qualityWarningCount"], 1)

    def test_smoke_summary_includes_quality_warning_count(self) -> None:
        summary = _redacted_summary(
            {
                "schemaVersion": "health-agent.run.v0",
                "runId": "run-test",
                "sessionId": "session-test",
                "status": "waiting_confirmation",
                "selectedSkill": "INITIAL_PLANNING",
                "finalOutcome": "waiting_confirmation",
                "trace": {"provider": "mock"},
                "output": _planning_output(),
                "memoryCandidates": [],
                "warnings": [
                    "quality:warning:aggressive_swimming_for_choking_risk:存在游泳风险。",
                ],
                "error": None,
            }
        )

        self.assertEqual(summary["warningCount"], 1)
        self.assertEqual(summary["qualityWarningCount"], 1)


def _planning_output(
    requires_confirmation: bool = True,
    weekly_plan: dict | None = None,
    today_action: dict | None = None,
) -> dict:
    return {
        "schemaVersion": "health-agent.initial-planning.v0",
        "summary": "生成待确认草案。",
        "understandingCandidates": [{"type": "status", "text": "想恢复训练"}],
        "healthConstraintCandidates": [{"name": "低强度起步"}],
        "goalCandidates": [{"name": "恢复规律训练"}],
        "programDraft": {"status": "draft_requires_confirmation"},
        "phaseDraft": {"status": "draft_requires_confirmation"},
        "weeklyPlanDraft": weekly_plan or _conservative_weekly_plan(),
        "todayActionDraft": today_action or _conservative_today_action(),
        "safetyNotes": ["需要确认后执行。"],
        "questions": [],
        "requiresUserConfirmation": requires_confirmation,
    }


def _conservative_weekly_plan() -> dict:
    return {
        "name": "首周低强度适应计划",
        "status": "draft_requires_confirmation",
        "focus": "适应、恢复、低强度、动作质量和呼吸节奏。",
        "days": [
            {
                "day": "周一",
                "items": [
                    {
                        "name": "轻松步行",
                        "prescription": "10分钟",
                        "note": "如疼痛、胸闷或头晕则停止。",
                    }
                ],
            }
        ],
        "downgradePlan": "不满足升级条件则重复当前周或只做恢复。",
    }


def _conservative_today_action() -> dict:
    return {
        "name": "今日行动草案",
        "title": "今日行动草案",
        "status": "draft_requires_confirmation",
        "minimumCompletionStandard": "最低完成：基线记录和10分钟恢复流程。",
        "downgradeRule": "不适则只做基线记录。",
        "stopConditions": ["胸闷、头晕或异常心悸则停止。"],
        "feedbackFields": ["血压", "静息心率", "不适评分"],
        "actions": [
            {
                "name": "基线记录",
                "detail": "记录血压、静息心率和不适评分。",
                "stopRule": "胸闷、头晕或异常心悸则停止。",
            }
        ],
    }


def _codes(result) -> set[str]:
    return {finding.code for finding in result.findings}


class _FakeProvider(BaseModelProvider):
    provider_name = "fake-openai-compatible"

    def __init__(self, output: dict) -> None:
        self.output = output

    def generate_initial_planning(self, prompt, planning_input):
        return self.output


if __name__ == "__main__":
    unittest.main()
