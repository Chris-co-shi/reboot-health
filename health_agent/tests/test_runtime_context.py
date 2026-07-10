import unittest
from datetime import datetime, timezone, timedelta

from agent.runtime.context import ContextBuilder, build_runtime_environment
from agent.runtime.session import AgentSession


class RuntimeContextTest(unittest.TestCase):
    def test_runtime_environment_uses_injected_datetime(self) -> None:
        fixed_now = datetime(
            2026,
            7,
            10,
            13,
            30,
            tzinfo=timezone(timedelta(hours=9)),
        )

        environment = build_runtime_environment(now=fixed_now, locale="zh-CN")

        self.assertEqual(environment.current_date, "2026-07-10")
        self.assertEqual(environment.timezone, "+09:00")
        self.assertEqual(environment.locale, "zh-CN")
        self.assertIn("2026-07-10T13:30:00", environment.current_datetime)

    def test_context_builder_injects_runtime_environment_into_skill_payload(self) -> None:
        fixed_now = datetime(
            2026,
            7,
            10,
            13,
            30,
            tzinfo=timezone(timedelta(hours=9)),
        )
        builder = ContextBuilder(now_provider=lambda: fixed_now)
        session = AgentSession(session_id="session-test")

        snapshot = builder.build(
            "INITIAL_PLANNING",
            {"userText": "想恢复训练", "locale": "zh-CN"},
            session,
        )

        runtime_payload = snapshot.skill_payload["runtimeEnvironment"]
        self.assertEqual(snapshot.skill_payload["today"], "2026-07-10")
        self.assertEqual(runtime_payload["currentDate"], "2026-07-10")
        self.assertEqual(runtime_payload["timezone"], "+09:00")


if __name__ == "__main__":
    unittest.main()
