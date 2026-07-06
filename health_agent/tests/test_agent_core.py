import unittest

from agent import AgentCore


class AgentCoreTest(unittest.TestCase):
    def test_unknown_trigger_returns_unsupported(self) -> None:
        core = AgentCore.default()

        result = core.run("UNKNOWN_TRIGGER", {"userText": "想开始恢复训练"})

        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["error"]["code"], "UNSUPPORTED_TRIGGER")
        self.assertFalse(result["requiresUserConfirmation"])

    def test_request_object_dispatches_initial_planning(self) -> None:
        core = AgentCore.default()

        result = core.run(
            {
                "trigger": "INITIAL_PLANNING",
                "input": {"userText": "体能差，游泳容易呛水，血压有点高。"},
            }
        )

        self.assertEqual(result["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertIn("weeklyPlanDraft", result)
        self.assertIn("todayActionDraft", result)


if __name__ == "__main__":
    unittest.main()
