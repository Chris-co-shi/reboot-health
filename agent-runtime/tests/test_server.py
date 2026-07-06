"""HTTP server 测试。"""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from agent_runtime.server import AgentRuntimeHandler


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), AgentRuntimeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def test_health(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)["status"], "UP")

    def test_execute_success(self) -> None:
        response = self.execute({"mockMode": "success"})

        self.assertEqual(response["schemaVersion"], "1.0")
        self.assertEqual(response["cards"][0]["title"], "AI教练服务已连接")

    def test_execute_invalid_structure_mode(self) -> None:
        response = self.execute({"mockMode": "invalid"})

        self.assertEqual(response["schemaVersion"], "invalid")

    def test_execute_timeout_mode(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.execute({"mockMode": "timeout"})
        self.assertEqual(error.exception.code, 504)

    def test_execute_failure_mode(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.execute({"mockMode": "failure"})
        self.assertEqual(error.exception.code, 500)

    def test_execute_rejects_missing_required_input(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/internal/v1/agent-runs/execute",
            data=json.dumps({"runId": "00000000-0000-0000-0000-000000000001"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=2)

        self.assertEqual(error.exception.code, 400)

    def execute(self, extra: dict[str, str]) -> dict[str, object]:
        payload = {
            "runId": "00000000-0000-0000-0000-000000000001",
            "userId": "00000000-0000-0000-0000-000000000002",
            "deviceId": "00000000-0000-0000-0000-000000000003",
            "triggerType": "TECHNICAL_SMOKE_TEST",
            "inputSummary": "技术链路检查",
        }
        payload.update(extra)
        request = urllib.request.Request(
            f"{self.base_url}/internal/v1/agent-runs/execute",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.load(response)


if __name__ == "__main__":
    unittest.main()
