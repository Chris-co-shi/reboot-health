"""OpenAI-compatible Provider 实现。

该实现是当前唯一允许的真实模型接入路径。它通过官方 openai Python SDK 调用
OpenAI-compatible Chat Completions API，并把返回 content 解析为 JSON-like 对象；
所有健康事实确认、安全规则和计划发布边界仍由 Skill/Schema 以及 Java Domain
Kernel 后续流程负责。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from agent.models.base import (
    BaseModelProvider,
    ProviderConfigurationError,
    ProviderResponseError,
)


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ProviderSDKResponse:
    """SDK 调用结果，只保留诊断所需的非敏感元数据。"""

    content: Any
    elapsed_ms: int
    payload_bytes: int


class OpenAICompatibleProvider(BaseModelProvider):
    """从环境变量配置的 OpenAI-compatible Chat Completions Provider。"""

    provider_name = "openai-compatible"

    BASE_URL_ENV = "REBOOT_HEALTH_MODEL_BASE_URL"
    API_KEY_ENV = "REBOOT_HEALTH_MODEL_API_KEY"
    MODEL_ENV = "REBOOT_HEALTH_MODEL_NAME"
    TIMEOUT_ENV = "REBOOT_HEALTH_MODEL_TIMEOUT_SECONDS"
    DEBUG_LOG_ENV = "REBOOT_HEALTH_MODEL_DEBUG_LOG"
    RESPONSE_FORMAT_ENV = "REBOOT_HEALTH_MODEL_RESPONSE_FORMAT"

    LEGACY_BASE_URL_ENV = "AGENT_OPENAI_BASE_URL"
    LEGACY_API_KEY_ENV = "AGENT_OPENAI_API_KEY"
    LEGACY_MODEL_ENV = "AGENT_OPENAI_MODEL"
    LEGACY_TIMEOUT_ENV = "AGENT_OPENAI_TIMEOUT_SECONDS"
    LEGACY_DEBUG_LOG_ENV = "AGENT_OPENAI_DEBUG_LOG"
    LEGACY_RESPONSE_FORMAT_ENV = "AGENT_OPENAI_RESPONSE_FORMAT"

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        debug_log: bool | None = None,
        client: Any | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        """读取 Provider 配置并创建 OpenAI SDK client。

        `env` 允许测试传入隔离字典；`client`/`client_factory` 用于单元测试注入，
        避免普通 unittest 访问真实网络。API Key 只保存在实例私有字段中，`repr`
        会主动打码。
        """
        source = os.environ if env is None else env
        self.base_url = _read_base_url(
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
        self.response_format = _read_response_format(
            _read_optional(
                source,
                self.RESPONSE_FORMAT_ENV,
                self.LEGACY_RESPONSE_FORMAT_ENV,
            )
        )
        self.debug_log = (
            _read_bool(
                _read_optional(source, self.DEBUG_LOG_ENV, self.LEGACY_DEBUG_LOG_ENV)
            )
            if debug_log is None
            else bool(debug_log)
        )
        self.last_request_shape: dict[str, Any] | None = None
        factory = client_factory or OpenAI
        self._client = client or factory(
            api_key=self._api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,
        )

    def generate_initial_planning(
        self,
        prompt: str,
        planning_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """调用 OpenAI-compatible 接口并解析 JSON 对象结果。"""
        return self.generate_json(prompt, planning_input, temperature=0.2)

    def generate_json(
        self,
        system_prompt: str,
        user_payload: Mapping[str, Any],
        temperature: float = 0.2,
    ) -> Mapping[str, Any]:
        """发送一次 JSON-oriented chat completion 并返回 JSON object。"""
        user_content = json.dumps(user_payload, ensure_ascii=False)
        response = self._send_chat_completion(
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=temperature,
        )
        return self._parse_model_content(response.content, response.elapsed_ms)

    def ping(self) -> Mapping[str, Any]:
        """发送极简 provider ping，用于排查 endpoint/model/key 基础链路。"""
        response = self._send_chat_completion(
            system_prompt='Return exactly this JSON object: {"ok": true}',
            user_content='{"ping": true}',
            temperature=0.0,
        )
        parsed = self._parse_model_content(response.content, response.elapsed_ms)
        if parsed.get("ok") is not True:
            raise ProviderResponseError(
                "OpenAI-compatible provider ping returned unexpected content",
                code="provider_response_error",
                safe_summary="OpenAI-compatible provider ping returned unexpected content",
            )
        return {
            "ok": True,
            "elapsedMs": response.elapsed_ms,
            "payloadBytes": response.payload_bytes,
            "responseFormat": self.response_format,
        }

    def _send_chat_completion(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float,
    ) -> _ProviderSDKResponse:
        """执行一次 SDK Chat Completions 请求，并只记录脱敏 request shape。"""
        request_kwargs = self._build_chat_kwargs(
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=temperature,
        )
        payload_bytes = len(
            json.dumps(request_kwargs, ensure_ascii=False, default=str).encode("utf-8")
        )
        request_shape = self._request_shape(
            request_kwargs=request_kwargs,
            payload_bytes=payload_bytes,
        )
        self.last_request_shape = dict(request_shape)
        started = time.monotonic()
        self._log_debug(
            "request_start",
            timeoutSeconds=self.timeout,
            **request_shape,
        )

        try:
            completion = self._client.chat.completions.create(**request_kwargs)
        except APITimeoutError as exc:
            self._raise_sdk_error(
                exc,
                code="timeout",
                safe_summary="OpenAI SDK request timed out",
                elapsed_ms=_elapsed_ms(started),
            )
        except RateLimitError as exc:
            self._raise_sdk_error(
                exc,
                code="rate_limit",
                safe_summary=_sdk_error_summary(exc),
                elapsed_ms=_elapsed_ms(started),
            )
        except APIStatusError as exc:
            self._raise_sdk_error(
                exc,
                code="http_error",
                safe_summary=_sdk_error_summary(exc),
                elapsed_ms=_elapsed_ms(started),
            )
        except APIConnectionError as exc:
            self._raise_sdk_error(
                exc,
                code="provider_response_error",
                safe_summary=_sdk_error_summary(exc),
                elapsed_ms=_elapsed_ms(started),
            )
        except APIError as exc:
            self._raise_sdk_error(
                exc,
                code="provider_response_error",
                safe_summary=_sdk_error_summary(exc),
                elapsed_ms=_elapsed_ms(started),
            )

        elapsed_ms = _elapsed_ms(started)
        content = _completion_content(completion)
        self._log_debug(
            "response_read",
            elapsedMs=elapsed_ms,
            contentChars=_content_chars(content),
            requestId=_completion_request_id(completion),
        )
        return _ProviderSDKResponse(
            content=content,
            elapsed_ms=elapsed_ms,
            payload_bytes=payload_bytes,
        )

    def _build_chat_kwargs(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float,
    ) -> dict[str, Any]:
        """生成 OpenAI SDK Chat Completions 参数。"""
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
        }
        if self.response_format == "json_object":
            request_kwargs["response_format"] = {"type": "json_object"}
        return request_kwargs

    def _request_shape(
        self,
        request_kwargs: Mapping[str, Any],
        payload_bytes: int,
    ) -> dict[str, Any]:
        """返回脱敏 request shape，不包含 prompt、用户原文、header 或密钥。"""
        messages = request_kwargs.get("messages")
        message_items = messages if isinstance(messages, list) else []
        system_prompt_chars = 0
        user_content_chars = 0
        if message_items:
            first = message_items[0]
            if isinstance(first, Mapping):
                system_prompt_chars = len(str(first.get("content") or ""))
            second = message_items[1] if len(message_items) > 1 else None
            if isinstance(second, Mapping):
                user_content_chars = len(str(second.get("content") or ""))
        response_format = request_kwargs.get("response_format")
        response_format_type = None
        if isinstance(response_format, Mapping):
            response_format_type = response_format.get("type")
        return {
            "endpoint": self._chat_completions_endpoint(),
            "model": request_kwargs.get("model"),
            "temperature": request_kwargs.get("temperature"),
            "responseFormatMode": self.response_format,
            "responseFormatPresent": "response_format" in request_kwargs,
            "responseFormatType": response_format_type,
            "stream": request_kwargs.get("stream"),
            "maxTokens": request_kwargs.get("max_tokens"),
            "messageCount": len(message_items),
            "systemPromptChars": system_prompt_chars,
            "userContentChars": user_content_chars,
            "payloadBytes": payload_bytes,
        }

    def _parse_model_content(
        self,
        content: Any,
        elapsed_ms: int,
    ) -> Mapping[str, Any]:
        """解析 SDK message content 为 JSON object。"""
        try:
            if isinstance(content, Mapping):
                parsed = dict(content)
            else:
                parsed = extract_json_object(str(content))
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            self._log_debug(
                "response_invalid_json",
                code="invalid_json",
                elapsedMs=elapsed_ms,
                errorType=type(exc).__name__,
                contentChars=_content_chars(content),
            )
            raise ProviderResponseError(
                "OpenAI-compatible provider returned invalid JSON content",
                code="invalid_json",
                safe_summary="OpenAI-compatible provider returned invalid JSON content",
            ) from exc
        self._log_debug(
            "response_parsed",
            elapsedMs=elapsed_ms,
            contentType="json_object",
            topLevelKeys=sorted(str(key) for key in parsed.keys()),
        )
        return parsed

    def _chat_completions_endpoint(self) -> str:
        """返回仅用于诊断展示的 endpoint；实际请求由 SDK base_url 管理。"""
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _raise_sdk_error(
        self,
        exc: Exception,
        code: str,
        safe_summary: str,
        elapsed_ms: int,
    ) -> None:
        """把 SDK 异常统一包装为 ProviderResponseError。"""
        self._log_debug(
            "request_sdk_error",
            code=code,
            elapsedMs=elapsed_ms,
            errorType=type(exc).__name__,
            safeSummary=safe_summary,
        )
        raise ProviderResponseError(
            safe_summary,
            code=code,
            safe_summary=safe_summary,
        ) from exc

    def __repr__(self) -> str:
        """返回不会泄漏 API Key 的调试表示。"""
        return (
            "OpenAICompatibleProvider("
            f"base_url={self.base_url!r}, model={self.model!r}, "
            f"response_format={self.response_format!r}, api_key=<redacted>)"
        )

    def _log_debug(self, event: str, **fields: Any) -> None:
        """输出安全诊断日志；不包含 API key、prompt、健康原文或响应正文。"""
        if not self.debug_log:
            return
        payload = {
            "event": event,
            "provider": self.provider_name,
            **_sanitize_log_fields(fields),
        }
        LOGGER.info(
            "openai_compatible_provider %s",
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
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


def _read_base_url(
    source: Mapping[str, str],
    name: str,
    legacy_name: str | None = None,
) -> str:
    """读取并校验 OpenAI SDK base_url。"""
    value = _read_required(source, name, legacy_name).rstrip("/")
    if value.endswith("/chat/completions"):
        raise ProviderConfigurationError(
            "REBOOT_HEALTH_MODEL_BASE_URL must be a base URL like "
            "https://api.minimaxi.com/v1, not a /chat/completions endpoint"
        )
    return value


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


def _read_response_format(value: str | None) -> str:
    """读取 response_format 模式；默认不发送 response_format 字段。"""
    if value is None or not str(value).strip():
        return "none"
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized in ("none", "off", "disabled", "false", "0"):
        return "none"
    if normalized == "json_object":
        return "json_object"
    raise ProviderConfigurationError(
        "Invalid provider response format: expected json_object or none"
    )


def _read_bool(value: str | None) -> bool:
    """读取布尔开关。"""
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on", "debug")


def _completion_content(completion: Any) -> Any:
    """从 OpenAI SDK completion 中提取 choices[0].message.content。"""
    try:
        return completion.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise ProviderResponseError(
            "OpenAI SDK completion response missing choices[0].message.content",
            code="invalid_json",
            safe_summary=(
                "OpenAI SDK completion response missing "
                "choices[0].message.content"
            ),
        ) from exc


def _completion_request_id(completion: Any) -> str | None:
    """读取 SDK response request id；没有则返回 None。"""
    value = getattr(completion, "_request_id", None)
    return str(value) if value else None


def _content_chars(content: Any) -> int:
    """返回 content 字符长度，不记录 content 本文。"""
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    return len(json.dumps(content, ensure_ascii=False, default=str))


def _elapsed_ms(started: float) -> int:
    """返回从 started 到当前的毫秒数。"""
    return max(0, int((time.monotonic() - started) * 1000))


def _sdk_error_summary(exc: Exception) -> str:
    """返回不含 header/key/body 的 SDK 错误摘要。"""
    status_code = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)
    parts = [f"OpenAI SDK error: {type(exc).__name__}"]
    if status_code:
        parts.append(f"status={status_code}")
    if request_id:
        parts.append(f"request_id={request_id}")
    return _redact_sensitive_text(", ".join(parts))


def _sanitize_log_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """递归清理日志字段，避免密钥、认证头或大段文本进入日志。"""
    sanitized: dict[str, Any] = {}
    for key, value in fields.items():
        key_text = str(key)
        if _is_sensitive_key(key_text):
            sanitized[key_text] = "<redacted>"
        else:
            sanitized[key_text] = _sanitize_log_value(value)
    return sanitized


def _sanitize_log_value(value: Any) -> Any:
    """清理日志值，仅保留短文本和结构化元数据。"""
    if isinstance(value, Mapping):
        return _sanitize_log_fields(value)
    if isinstance(value, list | tuple):
        return [_sanitize_log_value(item) for item in value[:20]]
    if isinstance(value, str):
        return _redact_sensitive_text(value)[:240]
    return value


def _is_sensitive_key(key: str) -> bool:
    """识别不允许进入日志的字段名。"""
    normalized = key.lower().replace("-", "_")
    return (
        normalized in {
            "authorization",
            "api_key",
            "apikey",
            "token",
            "secret",
            "password",
            "client_secret",
        }
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
    )


def _redact_sensitive_text(value: str) -> str:
    """对潜在敏感片段做最小脱敏，并压缩空白。"""
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer <redacted>", value)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-<redacted>", text)
    return " ".join(text.split())
