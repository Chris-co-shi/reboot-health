import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.agent_console import (
    ConsoleState,
    _handle_command,
    _load_profile_file_into_state,
    _run_agent,
    _run_summary,
    _save_run_summary,
)


USER_TEXT = "完整健康输入不应保存：我血压高，颈椎不舒服，想恢复训练。"


class AgentConsoleTest(unittest.TestCase):
    def test_run_agent_uses_agent_loop_with_mock_provider(self) -> None:
        state = ConsoleState(provider_name="mock", user_text=USER_TEXT)

        result = _run_agent(state)

        self.assertEqual(result["selectedSkill"], "INITIAL_PLANNING")
        self.assertEqual(result["finalOutcome"], "waiting_confirmation")
        self.assertTrue(result["output"]["requiresUserConfirmation"])
        step_names = [step["name"] for step in result["trace"]["steps"]]
        self.assertIn("context_built", step_names)
        self.assertIn("skill_started", step_names)

    def test_profile_load_and_commands_update_payload(self) -> None:
        state = ConsoleState(provider_name="mock")
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "userText": "想低强度恢复训练。",
                        "profile": {"age": 34},
                        "goals": [{"name": "恢复体能"}],
                        "knownHealthConstraints": [{"name": "血压偏高"}],
                        "preferences": {"trainingMode": "徒手"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            _load_profile_file_into_state(profile_path, state)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(_handle_command("/profile set heightCm=175", state))
            self.assertTrue(_handle_command("/goal add 减脂", state))
            self.assertTrue(_handle_command("/constraint add 颈椎不适", state))
            self.assertTrue(_handle_command("/preference set equipment=\"none\"", state))
        payload = state.to_payload()

        self.assertEqual(payload["profile"]["age"], 34)
        self.assertEqual(payload["profile"]["heightCm"], 175)
        self.assertEqual(payload["preferences"]["equipment"], "none")
        self.assertEqual(len(payload["goals"]), 2)
        self.assertEqual(len(payload["knownHealthConstraints"]), 2)

    def test_save_run_summary_redacts_user_text_and_api_key(self) -> None:
        api_key = "sk-placeholder-not-real"
        state = ConsoleState(provider_name="mock", user_text=USER_TEXT)
        with patch.dict(os.environ, {"REBOOT_HEALTH_MODEL_API_KEY": api_key}):
            _run_agent(state)
            with tempfile.TemporaryDirectory() as temp_dir:
                saved_path = _save_run_summary(state, Path(temp_dir) / "run.json")
                saved = saved_path.read_text(encoding="utf-8")

        self.assertIn("health-agent.console-run-summary.v0", saved)
        self.assertIn("traceSummary", saved)
        self.assertNotIn(USER_TEXT, saved)
        self.assertNotIn(api_key, saved)
        self.assertNotIn("prompt", saved.lower())
        self.assertNotIn("contentRaw", saved)

    def test_print_trace_summary_is_redacted(self) -> None:
        state = ConsoleState(provider_name="mock", user_text=USER_TEXT)

        _run_agent(state)
        summary = _run_summary(state, include_trace=True)

        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertIn("trace", summary)
        self.assertNotIn(USER_TEXT, serialized)
        self.assertIn("context_built", serialized)


if __name__ == "__main__":
    unittest.main()
