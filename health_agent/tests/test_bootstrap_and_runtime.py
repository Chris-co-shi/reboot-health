import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent.bootstrap import create_agent_core_from_env, create_generic_agent_loop_from_env
from agent.models import ModelResponse, OpenAICompatibleProvider, ProviderConfigurationError
from agent.runtime.core import AgentCore
from agent.runtime.generic_loop import GenericAgentLoop
from agent.runtime.loop import AgentLoop, LoopLimits
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.runtime.session import InMemorySessionStore
from agent.tools.builtin.convert_weight import CONVERT_WEIGHT_UNIT_TOOL_NAME
from agent.tools.contract import ToolPermission

from tests.support.scripted_model_provider import ScriptedModelProvider


class BootstrapAndRuntimeTest(unittest.TestCase):
    def test_bootstrap_missing_llm_environment_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_dotenv = Path(directory) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ProviderConfigurationError) as context:
                    create_agent_core_from_env(dotenv_path=missing_dotenv)

        self.assertIn("LLM_BASE_URL", str(context.exception))

    def test_generic_bootstrap_missing_llm_environment_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_dotenv = Path(directory) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ProviderConfigurationError) as context:
                    create_generic_agent_loop_from_env(dotenv_path=missing_dotenv)

        self.assertIn("LLM_BASE_URL", str(context.exception))

    def test_generic_bootstrap_wires_real_provider_and_convert_weight_tool(self) -> None:
        fake_client = Mock()
        with tempfile.TemporaryDirectory() as directory:
            missing_dotenv = Path(directory) / ".env"
            with patch.dict(os.environ, _llm_env(), clear=True):
                with patch("agent.models.openai_compatible.OpenAI", return_value=fake_client):
                    loop = create_generic_agent_loop_from_env(dotenv_path=missing_dotenv)

        self.assertIsInstance(loop, GenericAgentLoop)
        self.assertIsInstance(loop.provider, OpenAICompatibleProvider)
        self.assertIsInstance(loop.session_store, InMemorySessionStore)
        self.assertIsInstance(loop.pending_action_store, InMemoryPendingActionStore)
        self.assertIs(loop.tool_executor.registry, loop.tool_registry)

        definitions = loop.tool_registry.list()
        self.assertEqual([definition.name for definition in definitions], [CONVERT_WEIGHT_UNIT_TOOL_NAME])
        self.assertEqual(definitions[0].permission, ToolPermission.READ_ONLY)
        fake_client.chat.completions.create.assert_not_called()

    def test_generic_bootstrap_returns_independent_runtime_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_dotenv = Path(directory) / ".env"
            with patch.dict(os.environ, _llm_env(), clear=True):
                with patch("agent.models.openai_compatible.OpenAI", return_value=Mock()):
                    first = create_generic_agent_loop_from_env(dotenv_path=missing_dotenv)
                    second = create_generic_agent_loop_from_env(dotenv_path=missing_dotenv)

        self.assertIsNot(first, second)
        self.assertIsNot(first.tool_registry, second.tool_registry)
        self.assertIsNot(first.tool_executor, second.tool_executor)
        self.assertIsNot(first.session_store, second.session_store)
        self.assertIsNot(first.pending_action_store, second.pending_action_store)

    def test_agent_core_and_loop_require_injected_provider(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content=_planning_json())])

        core_result = AgentCore.default(provider=provider).run_detailed(
            "INITIAL_PLANNING",
            {"userText": "想低强度恢复训练"},
        )

        self.assertEqual(core_result.selected_skill, "INITIAL_PLANNING")
        self.assertEqual(core_result.final_outcome, "waiting_confirmation")
        self.assertEqual(len(provider.calls), 1)

        loop_provider = ScriptedModelProvider([ModelResponse(content=_planning_json())])
        loop_result = AgentLoop.default(
            provider=loop_provider,
            limits=LoopLimits(max_steps=1),
        ).run_detailed("INITIAL_PLANNING", {"userText": "想训练"})

        self.assertEqual(loop_result.status, "waiting_confirmation")
        self.assertEqual(len(loop_provider.calls), 1)

    def test_product_code_does_not_reference_test_provider_or_deleted_provider_file(self) -> None:
        product_root = Path(__file__).resolve().parents[1] / "agent"
        product_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in product_root.rglob("*.py")
            if "__pycache__" not in path.parts
        )

        self.assertNotIn("ScriptedModelProvider", product_text)
        self.assertFalse((product_root / "models" / ("mo" + "ck.py")).exists())
        self.assertNotIn("generate_" + "initial_planning", product_text)
        self.assertNotIn("agent.models." + "mo" + "ck", product_text)

    def test_bootstrap_does_not_load_test_support(self) -> None:
        import agent.bootstrap as bootstrap

        source = inspect.getsource(bootstrap)

        self.assertNotIn("tests.support", source)
        self.assertNotIn("ScriptedModelProvider", source)

    def test_agent_core_legacy_factory_is_still_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_dotenv = Path(directory) / ".env"
            with patch.dict(os.environ, _llm_env(), clear=True):
                with patch("agent.models.openai_compatible.OpenAI", return_value=Mock()):
                    core = create_agent_core_from_env(dotenv_path=missing_dotenv)

        self.assertIsInstance(core, AgentCore)
        self.assertIsNotNone(core.registry.get("INITIAL_PLANNING"))


def _llm_env() -> dict[str, str]:
    return {
        "LLM_BASE_URL": "https://llm.example.test/v1",
        "LLM_API_KEY": "test-api-key",
        "LLM_MODEL": "test-model",
    }


def _planning_json() -> str:
    return """
    {
      "schemaVersion": "health-agent.initial-planning.v0",
      "summary": "生成待确认草案。",
      "understandingCandidates": [],
      "healthConstraintCandidates": [],
      "goalCandidates": [],
      "programDraft": {"status": "draft_requires_confirmation"},
      "phaseDraft": {"status": "draft_requires_confirmation"},
      "weeklyPlanDraft": {
        "status": "draft_requires_confirmation",
        "days": []
      },
      "todayActionDraft": {
        "status": "draft_requires_confirmation",
        "title": "今日低强度行动草案",
        "actions": [{"name": "记录状态"}],
        "minimumCompletionStandard": "完成记录。",
        "downgradeRule": "状态不稳则只记录。",
        "stopConditions": ["胸闷或头晕时停止。"],
        "feedbackFields": ["疲劳程度"],
        "exclusions": ["不做高强度间歇。"]
      },
      "safetyNotes": [],
      "questions": [],
      "requiresUserConfirmation": true
    }
    """


if __name__ == "__main__":
    unittest.main()
