"""OpenAI-compatible Provider 实现。

该实现是当前唯一允许的真实模型接入路径。它只调用 OpenAI-compatible Chat
Completions API，并把返回内容解析为 JSON-like 对象；所有健康事实确认、安全规则
和计划发布边界仍由 Skill/Schema 以及 Java Domain Kernel 后续流程负责。
"""

from __future__ import annotations

import json
import os
import re
import socket
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

    provider_name = "openai-compatible"

    BASE_URL_ENV = "REBOOT_HEALTH_MODEL_BASE_URL"
    API_KEY_ENV = "REBOOT_HEALTH_MODEL_API_KEY"
    MODEL_ENV = "REBOOT_HEALTH_MODEL_NAME"
    TIMEOUT_ENV = "REBOOT_HEALTH_MODEL_TIMEOUT_SECONDS"

    LEGACY_BASE_URL_ENV = "AGENT_OPENAI_BASE_URL"
    LEGACY_API_KEY_ENV = "AGENT_OPENAI_API_KEY"
    LEGACY_MODEL_ENV = "AGENT_OPENAI_MODEL"
    LEGACY_TIMEOUT_ENV = "AGENT_OPENAI_TIMEOUT_SECONDS"

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        """读取 Provider 配置。

        `env` 允许测试传入隔离字典；生产路径默认读取 `os.environ`。API Key 只
        保存在实例私有字段中，`repr` 会主动打码。
        """
        source = os.environ if env is None else env
        self.base_url = _read_required(
            source,
            self.BASE_URL_ENV,
            self.LEGACY_BASE_URL_ENV,
        )
        self._api_key = _read_required(
            source,
            self.API_KEY_ENV,
            self.LEGACY_API_KEY_ENV,
        )
        self.model = _read_required(
            source,
            self.MODEL_ENV,
            self.LEGACY_MODEL_ENV,
        )
        self.timeout = _read_timeout(
            _read_optional(source, self.TIMEOUT_ENV, self.LEGACY_TIMEOUT_ENV)
        )

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
        except urllib.error.HTTPError as exc:
            summary = _http_error_summary(exc)
            raise ProviderResponseError(
                f"OpenAI-compatible provider request failed with HTTP {exc.code}",
                code="http_error",
                safe_summary=summary,
            ) from exc
        except urllib.error.URLError as exc:
            if _is_timeout(exc):
                raise ProviderResponseError(
                    "OpenAI-compatible provider request timed out",
                    code="timeout",
                    safe_summary="OpenAI-compatible provider request timed out",
                ) from exc
            raise ProviderResponseError(
                "OpenAI-compatible provider request failed",
                code="provider_response_error",
                safe_summary="OpenAI-compatible provider request failed",
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ProviderResponseError(
                "OpenAI-compatible provider request timed out",
                code="timeout",
                safe_summary="OpenAI-compatible provider request timed out",
            ) from exc

        try:
            response_body = json.loads(raw)
            content = response_body["choices"][0]["message"]["content"]
            if isinstance(content, Mapping):
                return dict(content)
            parsed = extract_json_object(str(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise ProviderResponseError(
                "OpenAI-compatible provider returned invalid JSON content",
                code="invalid_json",
                safe_summary="OpenAI-compatible provider returned invalid JSON content",
            ) from exc
        if not isinstance(parsed, Mapping):
            raise ProviderResponseError(
                "OpenAI-compatible provider content must be a JSON object",
                code="invalid_json",
                safe_summary="OpenAI-compatible provider content must be a JSON object",
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


def extract_json_object(text: str) -> Mapping[str, Any]:
    """从模型文本中提取第一个 JSON object。

    支持纯 JSON、```json 代码块，以及前后带少量解释文本的第一个 JSON object。
    解析失败会抛出 ValueError，不静默降级。
    """
    candidate = _extract_fenced_json(text) or _extract_first_object(text)
    if candidate is None:
        raise ValueError("No JSON object found in provider content")
    parsed = json.loads(candidate)
    if not isinstance(parsed, Mapping):
        raise ValueError("Provider content must be a JSON object")
    return dict(parsed)


def _extract_fenced_json(text: str) -> str | None:
    """提取 markdown fenced code block 中的 JSON。"""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if not match:
        return None
    return _extract_first_object(match.group(1))


def _extract_first_object(text: str) -> str | None:
    """通过括号计数提取第一个完整 JSON object。"""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _read_required(
    source: Mapping[str, str],
    name: str,
    legacy_name: str | None = None,
) -> str:
    """读取必填环境变量，优先新命名并兼容旧命名。"""
    value = _read_optional(source, name, legacy_name)
    if not value:
        if legacy_name:
            raise ProviderConfigurationError(
                f"Missing environment variable: {name} (legacy fallback: {legacy_name})"
            )
        raise ProviderConfigurationError(f"Missing environment variable: {name}")
    return value


def _read_optional(
    source: Mapping[str, str],
    name: str,
    legacy_name: str | None = None,
) -> str | None:
    """读取可选配置，优先新命名。"""
    value = str(source.get(name) or "").strip()
    if value:
        return value
    if legacy_name:
        legacy_value = str(source.get(legacy_name) or "").strip()
        if legacy_value:
            return legacy_value
    return None


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


def _is_timeout(exc: urllib.error.URLError) -> bool:
    """判断 URLError 是否由 timeout 引起。"""
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (TimeoutError, socket.timeout))


def _http_error_summary(exc: urllib.error.HTTPError) -> str:
    """返回不含 header/key 的 HTTP 错误短摘要。"""
    body = ""
    try:
        raw = exc.read(512)
        body = raw.decode("utf-8", errors="replace") if raw else ""
    except Exception:
        body = ""
    body = _redact_sensitive_text(body)
    if body:
        return f"HTTP {exc.code}: {body[:180]}"
    return f"HTTP {exc.code}"


def _redact_sensitive_text(value: str) -> str:
    """对潜在敏感片段做最小脱敏，并压缩空白。"""
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer <redacted>", value)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-<redacted>", text)
    return " ".join(text.split())
