import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.skills.initial_planning import _load_prompt
from scripts.smoke_initial_planning import (
    MINIMAL_CONTRACT_PROMPT,
    SAMPLE_PAYLOAD,
    _env_flag,
    _load_dotenv_file,
    _minimal_contract_payload,
    _parse_dotenv_line,
    _redacted_draft_summary,
    _redacted_summary,
)


FULL_USER_TEXT = "体能差，游泳容易呛水，血压有点高，想从低强度恢复训练。"


class SmokeInitialPlanningSummaryTest(unittest.TestCase):
    def test_smoke_default_summary_does_not_include_draft_details(self) -> None:
        summary = _redacted_summary(_agent_run_result())
        serialized = json.dumps(summary, ensure_ascii=False)

        self.assertNotIn("programDraft", summary)
        self.assertNotIn("phaseDraft", summary)
        self.assertNotIn("weeklyPlanDraft", summary)
        self.assertNotIn("todayActionDraft", summary)
        self.assertNotIn(FULL_USER_TEXT, serialized)

    def test_smoke_print_draft_summary_includes_draft_sections(self) -> None:
        summary = _redacted_draft_summary(
            _agent_run_result(),
            source_payload={"userText": FULL_USER_TEXT},
        )

        for key in (
            "programDraft",
            "phaseDraft",
            "weeklyPlanDraft",
            "todayActionDraft",
            "safetyNotes",
            "questions",
            "memoryCandidatesPreview",
            "warnings",
            "qualityWarningCount",
            "error",
        ):
            self.assertIn(key, summary)

    def test_smoke_print_draft_summary_does_not_include_api_key(self) -> None:
        api_key = "placeholder-not-a-real-api-key"
        result = _agent_run_result(secret_text=api_key)

        with patch.dict(os.environ, {"REBOOT_HEALTH_MODEL_API_KEY": api_key}):
            summary = _redacted_draft_summary(
                result,
                source_payload={"userText": FULL_USER_TEXT},
            )

        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn(api_key, serialized)
        self.assertIn("<redacted>", serialized)

    def test_smoke_print_draft_summary_does_not_include_full_user_text(self) -> None:
        result = _agent_run_result(include_user_text=True)

        summary = _redacted_draft_summary(
            result,
            source_payload={"userText": FULL_USER_TEXT},
        )

        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn(FULL_USER_TEXT, serialized)
        self.assertIn("<redacted-health-input>", serialized)

    def test_smoke_print_draft_summary_includes_quality_warning_count(self) -> None:
        summary = _redacted_draft_summary(
            _agent_run_result(
                warnings=[
                    "quality:warning:hiit_for_low_fitness:基础体能很低时不建议 HIIT。",
                    "provider warning",
                ]
            ),
            source_payload={"userText": FULL_USER_TEXT},
        )

        self.assertEqual(summary["warningCount"], 2)
        self.assertEqual(summary["qualityWarningCount"], 1)

    def test_model_debug_log_env_flag_is_supported(self) -> None:
        with patch.dict(os.environ, {"REBOOT_HEALTH_MODEL_DEBUG_LOG": "1"}):
            self.assertTrue(_env_flag("REBOOT_HEALTH_MODEL_DEBUG_LOG"))

    def test_smoke_loads_model_config_from_dotenv(self) -> None:
        keys = (
            "REBOOT_HEALTH_AGENT_PROVIDER",
            "REBOOT_HEALTH_MODEL_BASE_URL",
            "REBOOT_HEALTH_MODEL_API_KEY",
            "REBOOT_HEALTH_MODEL_NAME",
            "REBOOT_HEALTH_MODEL_TIMEOUT_SECONDS",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    (
                        "REBOOT_HEALTH_AGENT_PROVIDER=openai-compatible",
                        "REBOOT_HEALTH_MODEL_BASE_URL=https://model.example/v1",
                        "REBOOT_HEALTH_MODEL_API_KEY=placeholder-test-key",
                        "REBOOT_HEALTH_MODEL_NAME=test-model",
                        "REBOOT_HEALTH_MODEL_TIMEOUT_SECONDS=120",
                    )
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=False):
                for key in keys:
                    os.environ.pop(key, None)
                loaded = _load_dotenv_file(dotenv_path)
                self.assertEqual(set(loaded), set(keys))
                self.assertEqual(
                    os.environ["REBOOT_HEALTH_AGENT_PROVIDER"],
                    "openai-compatible",
                )
                self.assertEqual(
                    os.environ["REBOOT_HEALTH_MODEL_BASE_URL"],
                    "https://model.example/v1",
                )
                self.assertEqual(
                    os.environ["REBOOT_HEALTH_MODEL_API_KEY"],
                    "placeholder-test-key",
                )
                self.assertEqual(os.environ["REBOOT_HEALTH_MODEL_NAME"], "test-model")
                self.assertEqual(
                    os.environ["REBOOT_HEALTH_MODEL_TIMEOUT_SECONDS"],
                    "120",
                )

    def test_dotenv_does_not_override_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "REBOOT_HEALTH_MODEL_NAME=dotenv-model\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"REBOOT_HEALTH_MODEL_NAME": "shell-model"},
                clear=False,
            ):
                loaded = _load_dotenv_file(dotenv_path)
                self.assertEqual(os.environ["REBOOT_HEALTH_MODEL_NAME"], "shell-model")

            self.assertEqual(loaded, ())

    def test_dotenv_parser_supports_export_quotes_and_comments(self) -> None:
        self.assertEqual(
            _parse_dotenv_line('export REBOOT_HEALTH_MODEL_NAME="test-model"'),
            ("REBOOT_HEALTH_MODEL_NAME", "test-model"),
        )
        self.assertEqual(
            _parse_dotenv_line("REBOOT_HEALTH_MODEL_TIMEOUT_SECONDS=120 # comment"),
            ("REBOOT_HEALTH_MODEL_TIMEOUT_SECONDS", "120"),
        )
        self.assertIsNone(_parse_dotenv_line("# comment"))

    def test_smoke_contract_mode_minimal_uses_smaller_contract_if_implemented(self) -> None:
        full_prompt = _load_prompt()
        minimal_payload = _minimal_contract_payload()
        serialized_payload = json.dumps(minimal_payload, ensure_ascii=False)

        self.assertLess(len(MINIMAL_CONTRACT_PROMPT), len(full_prompt))
        self.assertIn("todayActionDraft", MINIMAL_CONTRACT_PROMPT)
        self.assertNotIn("weeklyPlanDraft", MINIMAL_CONTRACT_PROMPT)
        self.assertNotIn("weeklyPlanDraft", serialized_payload)

    def test_smoke_default_input_contains_real_health_baseline_without_printing_it(self) -> None:
        text = SAMPLE_PAYLOAD["userText"]
        for phrase in (
            "34岁",
            "175cm",
            "约93kg",
            "肚子大",
            "游泳25米都勉强",
            "换气容易呛水",
            "颈椎有问题",
            "医生建议游泳",
            "肌肉质量差",
            "篮球两个回合就喘",
            "血压135-145/85-95",
            "减脂",
            "恢复体能",
            "恢复基础力量",
            "徒手为主",
            "健身房辅助",
        ):
            self.assertIn(phrase, text)

        summary = _redacted_summary(_agent_run_result(include_user_text=True))
        serialized = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn(FULL_USER_TEXT, serialized)


def _agent_run_result(
    include_user_text: bool = False,
    secret_text: str | None = None,
    warnings: list[str] | None = None,
) -> dict:
    sensitive_detail = []
    if include_user_text:
        sensitive_detail.append(FULL_USER_TEXT)
    if secret_text:
        sensitive_detail.append(f"Bearer {secret_text}")
    detail = "；".join(sensitive_detail) or "低强度起步，等待用户确认。"
    return {
        "schemaVersion": "health-agent.run.v0",
        "runId": "run-test",
        "sessionId": "session-test",
        "status": "waiting_confirmation",
        "selectedSkill": "INITIAL_PLANNING",
        "finalOutcome": "waiting_confirmation",
        "trace": {
            "provider": "mock",
            "steps": [{"name": "context_built", "input": FULL_USER_TEXT}],
        },
        "output": {
            "schemaVersion": "health-agent.initial-planning.v0",
            "requiresUserConfirmation": True,
            "programDraft": {
                "status": "draft_requires_confirmation",
                "principles": ["低强度", "循序渐进", detail],
            },
            "phaseDraft": {
                "status": "draft_requires_confirmation",
                "focus": ["恢复节奏", "呼吸适应"],
            },
            "weeklyPlanDraft": {
                "status": "draft_requires_confirmation",
                "focus": "首周低强度适应。",
                "downgradePlan": "不适则停止或降级。",
            },
            "todayActionDraft": {
                "status": "draft_requires_confirmation",
                "minimumCompletionStandard": "最低完成：基线记录。",
            },
            "safetyNotes": ["需要确认后执行。"],
            "questions": ["是否有胸闷、头晕或异常心悸？"],
        },
        "memoryCandidates": [
            {
                "kind": "understanding",
                "content": FULL_USER_TEXT if include_user_text else "低强度恢复训练",
                "confidence": 0.7,
                "requiresUserConfirmation": True,
            }
        ],
        "warnings": warnings or [],
        "error": None,
    }


if __name__ == "__main__":
    unittest.main()
