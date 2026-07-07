import json
import os
import unittest
from unittest.mock import patch

from agent import AgentCore
from agent.runtime.loop import AgentLoop, LoopLimits
from agent.runtime.result import AgentRunResult
from agent.schemas.agent import (
    AGENT_RUN_SCHEMA_VERSION,
    AGENT_RUN_STATUS_ERROR,
    AGENT_RUN_STATUS_UNSUPPORTED,
    AGENT_RUN_STATUS_WAITING_CONFIRMATION,
    FINAL_OUTCOME_MAX_STEPS_EXCEEDED,
    FINAL_OUTCOME_UNSUPPORTED,
    FINAL_OUTCOME_WAITING_CONFIRMATION,
)


class AgentRunResultContractTest(unittest.TestCase):
    def test_run_detailed_returns_agent_run_result(self) -> None:
        result = AgentLoop.default().run_detailed(
            "INITIAL_PLANNING",
            {"userText": "想低强度恢复训练。"},
        )

        self.assertIsInstance(result, AgentRunResult)
        self.assertEqual(result.schema_version, AGENT_RUN_SCHEMA_VERSION)
        self.assertTrue(result.run_id.startswith("run-"))
        self.assertTrue(result.session_id.startswith("session-"))
        self.assertEqual(result.status, AGENT_RUN_STATUS_WAITING_CONFIRMATION)
        self.assertEqual(result.selected_skill, "INITIAL_PLANNING")
        self.assertEqual(result.final_outcome, FINAL_OUTCOME_WAITING_CONFIRMATION)

    def test_agent_run_result_contains_output(self) -> None:
        result = AgentLoop.default().run_detailed(
            "INITIAL_PLANNING",
            {"userText": "体能差，想恢复训练。"},
        )

        self.assertIsNotNone(result.output)
        self.assertEqual(result.output["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertIn("weeklyPlanDraft", result.output)
        self.assertTrue(result.to_dict()["output"]["requiresUserConfirmation"])

    def test_agent_run_result_contains_trace_summary(self) -> None:
        result = AgentLoop.default().run_detailed(
            "INITIAL_PLANNING",
            {"userText": "想训练。"},
        )

        trace = result.to_dict()["trace"]
        self.assertEqual(trace["runId"], result.run_id)
        self.assertEqual(trace["sessionId"], result.session_id)
        self.assertEqual(trace["triggerType"], "INITIAL_PLANNING")
        self.assertEqual(trace["selectedSkill"], "INITIAL_PLANNING")
        self.assertEqual(trace["finalOutcome"], FINAL_OUTCOME_WAITING_CONFIRMATION)
        self.assertEqual(trace["provider"], "mock")

    def test_trace_summary_contains_l2_steps_without_sensitive_content(self) -> None:
        user_text = "这是一段不应进入 trace 的完整健康原文，包含血压和训练偏好。"
        api_key = "placeholder-not-a-real-api-key"

        with patch.dict(os.environ, {"REBOOT_HEALTH_MODEL_API_KEY": api_key}):
            result = AgentLoop.default().run_detailed(
                "INITIAL_PLANNING",
                {"userText": user_text},
            )

        trace = result.to_dict()["trace"]
        step_names = [step["name"] for step in trace["steps"]]
        for name in (
            "run_started",
            "context_built",
            "skill_selected",
            "skill_started",
            "provider_request_sent",
            "provider_response_received",
            "provider_json_parsed",
            "skill_provider_output_received",
            "skill_output_mapped",
            "runtime_boundaries_applied",
            "schema_validated",
            "quality_gate_checked",
            "memory_candidates_built",
            "run_finished",
        ):
            self.assertIn(name, step_names)

        serialized = json.dumps(trace, ensure_ascii=False)
        self.assertNotIn(user_text, serialized)
        self.assertNotIn(api_key, serialized)

    def test_agent_run_result_contains_memory_candidates(self) -> None:
        result = AgentLoop.default().run_detailed(
            "INITIAL_PLANNING",
            {"userText": "颈椎不舒服，想低强度恢复。"},
        )

        payload = result.to_dict()
        self.assertGreater(len(payload["memoryCandidates"]), 0)
        for candidate in payload["memoryCandidates"]:
            self.assertTrue(candidate["requiresUserConfirmation"])
            self.assertIn(candidate["kind"], ("understanding", "health_constraint", "goal"))

    def test_unsupported_trigger_returns_structured_result(self) -> None:
        result = AgentLoop.default().run_detailed(
            "UNKNOWN_TRIGGER",
            {"userText": "想训练。"},
        )

        self.assertEqual(result.status, AGENT_RUN_STATUS_UNSUPPORTED)
        self.assertEqual(result.final_outcome, FINAL_OUTCOME_UNSUPPORTED)
        self.assertIsNone(result.selected_skill)
        self.assertEqual(result.error.code, "UNSUPPORTED_TRIGGER")
        self.assertEqual(result.output["status"], "unsupported")
        self.assertEqual(result.to_dict()["error"]["code"], "UNSUPPORTED_TRIGGER")

    def test_max_steps_exceeded_returns_structured_result(self) -> None:
        loop = AgentLoop.default(limits=LoopLimits(max_steps=0))

        result = loop.run_detailed(
            "INITIAL_PLANNING",
            {"userText": "想训练。"},
        )

        self.assertEqual(result.status, AGENT_RUN_STATUS_ERROR)
        self.assertEqual(result.final_outcome, FINAL_OUTCOME_MAX_STEPS_EXCEEDED)
        self.assertEqual(result.error.code, "MAX_STEPS_EXCEEDED")
        self.assertIn("max_steps_exceeded", result.warnings)
        self.assertEqual(result.output["error"]["code"], "MAX_STEPS_EXCEEDED")

    def test_agent_core_run_remains_backward_compatible(self) -> None:
        result = AgentCore.default().run(
            "INITIAL_PLANNING",
            {"userText": "体能差，游泳容易呛水，血压有点高。"},
        )

        self.assertEqual(result["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertIn("weeklyPlanDraft", result)
        self.assertNotIn("runId", result)
        self.assertNotIn("warnings", result)


if __name__ == "__main__":
    unittest.main()
