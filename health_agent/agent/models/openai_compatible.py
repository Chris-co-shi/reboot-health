"""OpenAI-compatible Provider 实现。

该实现用于保持 Provider 接口的可扩展性。当前任务和测试不会实例化真实请求路径；
真正启用时仍必须通过环境变量显式配置，并由 Skill/Schema 继续执行输出边界校验。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

from agent.models.base import (
    BaseModelProvider,
    ProviderConfigurationError,
    ProviderResponseError,
)


class OpenAICompatibleProvider(BaseModelProvider):
    """从环境变量配置的 OpenAI-compatible Chat Completions Provider。"""

    provider_name = "openai_compatible"

    BASE_URL_ENV = "AGENT_OPENAI_BASE_URL"
    API_KEY_ENV = "AGENT_OPENAI_API_KEY"
    MODEL_ENV = "AGENT_OPENAI_MODEL"
    TIMEOUT_ENV = "AGENT_OPENAI_TIMEOUT_SECONDS"

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        """读取 Provider 配置。

        `env` 允许测试传入隔离字典；生产路径默认读取 `os.environ`。API Key 只
        保存在实例私有字段中，`repr` 会主动打码。
        """
        source = os.environ if env is None else env
        self.base_url = _read_required(source, self.BASE_URL_ENV)
        self._api_key = _read_required(source, self.API_KEY_ENV)
        self.model = _read_required(source, self.MODEL_ENV)
        self.timeout = _read_timeout(source.get(self.TIMEOUT_ENV))

    def generate_initial_planning(
        self,
        prompt: str,
        planning_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """调用 OpenAI-compatible 接口并解析 JSON 对象结果。

        返回内容必须是 JSON object；解析失败统一转为 ProviderResponseError，交由
        AgentCore 归一化为结构化错误。
        """
        request_body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(planning_input, ensure_ascii=False),
                },
            ],
        }
        request = urllib.request.Request(
            self._endpoint(),
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise ProviderResponseError("OpenAI-compatible provider request failed") from exc

        try:
            response_body = json.loads(raw)
            content = response_body["choices"][0]["message"]["content"]
            if isinstance(content, Mapping):
                return dict(content)
            parsed = json.loads(str(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderResponseError(
                "OpenAI-compatible provider returned invalid JSON content"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise ProviderResponseError(
                "OpenAI-compatible provider content must be a JSON object"
            )
        return dict(parsed)

    def _endpoint(self) -> str:
        """拼出 Chat Completions endpoint，兼容传入完整路径或 base URL。"""
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def __repr__(self) -> str:
        """返回不会泄漏 API Key 的调试表示。"""
        return (
            "OpenAICompatibleProvider("
            f"base_url={self.base_url!r}, model={self.model!r}, "
            "api_key=<redacted>)"
        )


def _read_required(source: Mapping[str, str], name: str) -> str:
    """读取必填环境变量，缺失时抛出配置错误。"""
    value = str(source.get(name) or "").strip()
    if not value:
        raise ProviderConfigurationError(f"Missing environment variable: {name}")
    return value


def _read_timeout(value: str | None) -> float:
    """读取超时秒数；缺省使用保守默认值 30 秒。"""
    if value is None or not str(value).strip():
        return 30.0
    try:
        timeout = float(value)
    except ValueError as exc:
        raise ProviderConfigurationError("Invalid provider timeout") from exc
    if timeout <= 0:
        raise ProviderConfigurationError("Provider timeout must be positive")
    return timeout
