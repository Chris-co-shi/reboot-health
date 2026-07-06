"""标准库 HTTP Agent Runtime。"""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from agent_runtime.model_provider import MockProvider
from agent_runtime.models import ExecuteRequest


class AgentRuntimeHandler(BaseHTTPRequestHandler):
    """Agent Runtime HTTP handler。"""

    provider = MockProvider()

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "UP"})
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/internal/v1/agent-runs/execute":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            request = ExecuteRequest.from_json(self._read_json())
            response = self.provider.execute(request)
            self._write_json(HTTPStatus.OK, response.to_json())
        except TimeoutError:
            self._write_json(HTTPStatus.GATEWAY_TIMEOUT, {"error": "mock_timeout"})
        except KeyError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "field": str(exc)})
        except Exception:
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "mock_internal_failure"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """避免默认日志输出请求体或敏感上下文。"""

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body or "{}")
        if not isinstance(data, dict):
            raise ValueError("request body must be an object")
        return data

    def _write_json(self, status: HTTPStatus, data: dict[str, Any]) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run(host: str, port: int) -> None:
    """启动 Agent Runtime。"""

    server = ThreadingHTTPServer((host, port), AgentRuntimeHandler)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
