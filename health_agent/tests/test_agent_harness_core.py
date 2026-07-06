import unittest

from agent import AgentCore
from agent.runtime.loop import AgentLoop, LoopLimits
from agent.runtime.state import RunStatus
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry


class AgentHarnessCoreTest(unittest.TestCase):
    def test_agent_loop_runs_initial_planning(self) -> None:
        loop = AgentLoop.default()

        result = loop.run(
            {
                "trigger": "INITIAL_PLANNING",
                "input": {"userText": "体能差，游泳容易呛水，想恢复训练。"},
            }
        )

        self.assertEqual(result["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertIn("weeklyPlanDraft", result)
        self.assertIsNotNone(loop.last_session)
        self.assertEqual(loop.last_session.current_skill, "INITIAL_PLANNING")
        self.assertEqual(loop.last_session.status, RunStatus.WAITING_CONFIRMATION)
        self.assertEqual(loop.last_session.turns, 1)

    def test_agent_loop_rejects_unknown_trigger(self) -> None:
        result = AgentLoop.default().run(
            {"trigger": "UNKNOWN_TRIGGER", "input": {"userText": "想训练"}}
        )

        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["error"]["code"], "UNSUPPORTED_TRIGGER")
        self.assertFalse(result["requiresUserConfirmation"])

    def test_agent_loop_stops_at_max_steps(self) -> None:
        loop = AgentLoop.default(limits=LoopLimits(max_steps=0))

        result = loop.run(
            {"trigger": "INITIAL_PLANNING", "input": {"userText": "想训练"}}
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "MAX_STEPS_EXCEEDED")
        self.assertEqual(loop.last_session.status, RunStatus.FAILED)
        self.assertEqual(loop.last_trace.final_outcome, "max_steps_exceeded")

    def test_tool_executor_rejects_unregistered_tool(self) -> None:
        executor = ToolExecutor(ToolRegistry())

        with self.assertRaises(KeyError):
            executor.execute("unregistered.tool", {"value": 1})

    def test_trace_records_selected_skill_and_final_outcome(self) -> None:
        loop = AgentLoop.default()

        loop.run({"trigger": "INITIAL_PLANNING", "input": {"userText": "想训练"}})

        trace = loop.last_trace.to_dict()
        self.assertEqual(trace["selectedSkill"], "INITIAL_PLANNING")
        self.assertEqual(trace["finalOutcome"], "waiting_confirmation")
        self.assertEqual(trace["triggerType"], "INITIAL_PLANNING")

    def test_memory_candidate_requires_confirmation(self) -> None:
        loop = AgentLoop.default()

        loop.run(
            {
                "trigger": "INITIAL_PLANNING",
                "input": {"userText": "颈椎不舒服，想低强度恢复。"},
            }
        )

        self.assertGreater(len(loop.last_memory_candidates), 0)
        for candidate in loop.last_memory_candidates:
            self.assertTrue(candidate.requires_user_confirmation)

    def test_existing_initial_planning_still_passes(self) -> None:
        result = AgentCore.default().run(
            {
                "trigger": "INITIAL_PLANNING",
                "input": {"userText": "体能差，游泳容易呛水，血压有点高。"},
            }
        )

        self.assertEqual(result["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertEqual(result["weeklyPlanDraft"]["status"], "draft_requires_confirmation")
        self.assertEqual(result["todayActionDraft"]["status"], "draft_requires_confirmation")


if __name__ == "__main__":
    unittest.main()
