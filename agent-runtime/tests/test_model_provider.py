"""Model Mock 测试。"""

from __future__ import annotations

import unittest

from agent_runtime.model_provider import MockProvider
from agent_runtime.models import ExecuteRequest


class MockProviderTest(unittest.TestCase):
    def request(self, mode: str | None = None) -> ExecuteRequest:
        return ExecuteRequest(
            run_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            device_id="00000000-0000-0000-0000-000000000003",
            trigger_type="TECHNICAL_SMOKE_TEST",
            input_summary="技术链路检查",
            mock_mode=mode,
        )

    def test_success(self) -> None:
        response = MockProvider().execute(self.request())

        self.assertEqual(response.schema_version, "1.0")
        self.assertEqual(response.cards[0].type, "SYSTEM_STATUS")

    def test_invalid(self) -> None:
        response = MockProvider().execute(self.request("invalid"))

        self.assertEqual(response.schema_version, "invalid")
        self.assertEqual(response.cards, [])

    def test_timeout(self) -> None:
        with self.assertRaises(TimeoutError):
            MockProvider().execute(self.request("timeout"))

    def test_failure(self) -> None:
        with self.assertRaises(RuntimeError):
            MockProvider().execute(self.request("failure"))


if __name__ == "__main__":
    unittest.main()
