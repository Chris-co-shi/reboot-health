"""OpenAI-compatible Chat Completions Provider。

Provider 只负责调用模型并把 Chat Completions 响应转换为通用 ModelResponse。
它不理解 INITIAL_PLANNING、Program、Phase、WeeklyPlan 或 TodayAction。
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Mapping, Sequence

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from agent.config import LLMSettings
from agent.models.base import (
    ModelMessage,
    ModelOptions,
    ModelProvider,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
    ProviderConfigurationError,
    ProviderResponseError,
    mutable_mapping,
)


LOGGER = logging.getLogger(__name__)


class OpenAICompatibleProvider(ModelProvider):
    """由已验证 settings 配置的 OpenAI-compatible Provider。"""

    provider_name = "openai-compatible"

    def __init__(
        self,
        settings: LLMSettings,
        *,
        debug_log: bool = False,
        response_format: str | None = None,
        log_request: str | None = None,
        log_response: str | None = None,
        client: Any | None = None,
        client_factory: Any | None = None,
    ) -> None:
        self.settings = settings
        self.base_url = settings.base_url
        self._api_key = settings.api_key
        self.model = settings.model
        self.timeout = settings.timeout_seconds
        self.response_format = _read_response_format(response_format)
        self.log_request = _read_log_payload(log_request)
        self.log_response = _read_log_payload(log_response)
        self.debug_log = bool(debug_log)
        self.last_request_shape: dict[str, Any] | None = None
        factory = client_factory or OpenAI
        self._client = client or factory(
            api_key=self._api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,
        )

    def complete_turn(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition] = (),
        options: ModelOptions | None = None,
    ) -> ModelResponse:
        """执行一次 Chat Completions 模型回合。"""
        request_kwargs = self._build_chat_kwargs(messages, tools, options or ModelOptions())
        payload_bytes = len(
            json.dumps(request_kwargs, ensure_ascii=False, default=str).encode("utf-8")
        )
        request_shape = self._request_shape(request_kwargs, payload_bytes)
        self.last_request_shape = dict(request_shape)
        self._log_request_built(request_kwargs)
        started = time.monotonic()
        self._log_debug("request_start", timeoutSeconds=self.timeout, **request_shape)

        try:
            completion = self._client.chat.completions.create(**request_kwargs)
        except APITimeoutError as exc:
            self._raise_sdk_error(
                exc,
                code="timeout",
                safe_summary="OpenAI-compatible provider request timed out",
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
        response = self._to_model_response(completion, elapsed_ms, payload_bytes)
        self._log_response_content(response.content)
        self._log_debug(
            "response_read",
            elapsedMs=elapsed_ms,
            contentChars=len(response.content or ""),
            toolCallCount=len(response.tool_calls),
            finishReason=response.finish_reason,
            requestId=response.provider_metadata.get("requestId"),
        )
        return response

    def ping(self) -> Mapping[str, Any]:
        """发送极简模型调用，用于验证 Provider 基础链路。"""
        response = self.complete_turn(
            messages=(
                ModelMessage(role="system", content="Return exactly: ok"),
                ModelMessage(role="user", content="ping"),
            ),
            options=ModelOptions(temperature=0.0),
        )
        if not (response.content or "").strip():
            raise ProviderResponseError(
                "OpenAI-compatible provider ping returned empty content",
                code="provider_response_error",
                safe_summary="OpenAI-compatible provider ping returned empty content",
            )
        return {
            "ok": True,
            "finishReason": response.finish_reason,
            "usage": response.usage,
            "providerMetadata": response.provider_metadata,
        }

    def _build_chat_kwargs(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition],
        options: ModelOptions,
    ) -> dict[str, Any]:
        if not messages:
            raise ProviderResponseError(
                "Model turn requires at least one message",
                code="invalid_request",
                safe_summary="Model turn requires at least one message",
            )
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_to_openai(message) for message in messages],
        }
        if options.temperature is not None:
            request_kwargs["temperature"] = options.temperature
        if options.max_tokens is not None:
            request_kwargs["max_tokens"] = options.max_tokens
        response_format = options.response_format or self.response_format
        if response_format == "json_object":
            request_kwargs["response_format"] = {"type": "json_object"}
        if tools:
            request_kwargs["tools"] = [_tool_to_openai(tool) for tool in tools]
        return request_kwargs

    def _to_model_response(
        self,
        completion: Any,
        elapsed_ms: int,
        payload_bytes: int,
    ) -> ModelResponse:
        choice = _first_choice(completion)
        message = _value(choice, "message")
        if message is None:
            raise ProviderResponseError(
                "OpenAI-compatible provider returned no assistant message",
                code="provider_response_error",
                safe_summary="OpenAI-compatible provider returned no assistant message",
            )
        content = _content_text(_value(message, "content"))
        tool_calls = tuple(_parse_tool_calls(_value(message, "tool_calls")))
        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=str(_value(choice, "finish_reason") or "unknown"),
            usage=_parse_usage(_value(completion, "usage")),
            provider_metadata={
                "provider": self.provider_name,
                "model": _value(completion, "model") or self.model,
                "requestId": _completion_request_id(completion),
                "elapsedMs": elapsed_ms,
                "payloadBytes": payload_bytes,
                "endpoint": self._chat_completions_endpoint(),
            },
        )

    def _request_shape(
        self,
        request_kwargs: Mapping[str, Any],
        payload_bytes: int,
    ) -> dict[str, Any]:
        messages = request_kwargs.get("messages")
        message_items = messages if isinstance(messages, list) else []
        tool_items = request_kwargs.get("tools")
        response_format = request_kwargs.get("response_format")
        response_format_type = (
            response_format.get("type") if isinstance(response_format, Mapping) else None
        )
        return {
            "endpoint": self._chat_completions_endpoint(),
            "model": request_kwargs.get("model"),
            "temperature": request_kwargs.get("temperature"),
            "responseFormatMode": self.response_format,
            "responseFormatPresent": "response_format" in request_kwargs,
            "responseFormatType": response_format_type,
            "messageCount": len(message_items),
            "toolCount": len(tool_items) if isinstance(tool_items, list) else 0,
            "payloadBytes": payload_bytes,
        }

    def _chat_completions_endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _raise_sdk_error(
        self,
        exc: Exception,
        code: str,
        safe_summary: str,
        elapsed_ms: int,
    ) -> None:
        safe_summary = _redact_sensitive_text(
            safe_summary,
            extra_secrets=(self._api_key,),
        )
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
        return (
            "OpenAICompatibleProvider("
            f"base_url={self.base_url!r}, model={self.model!r}, api_key=<redacted>)"
        )

    def _log_debug(self, event: str, **fields: Any) -> None:
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

    def _log_request_built(self, request_kwargs: Mapping[str, Any]) -> None:
        messages = request_kwargs.get("messages")
        message_items = messages if isinstance(messages, list) else []
        payload: dict[str, Any] = {
            "mode": self.log_request,
            "model": request_kwargs.get("model"),
            "messageCount": len(message_items),
            "toolCount": len(request_kwargs.get("tools") or []),
            "responseFormatPresent": "response_format" in request_kwargs,
        }
        if self.log_request == "none":
            self._log_debug("provider_request_built", **payload)
            return
        text = json.dumps(message_items, ensure_ascii=False, default=str)
        safe_text = _redact_sensitive_text(text, extra_secrets=(self._api_key,))
        if self.log_request == "raw":
            payload["messagesRaw"] = safe_text
        else:
            payload["messagesPreview"] = safe_text[:2000]
        self._log_debug("provider_request_built", **payload)

    def _log_response_content(self, content: str | None) -> None:
        text = content or ""
        payload: dict[str, Any] = {
            "mode": self.log_response,
            "contentChars": len(text),
        }
        if self.log_response == "none":
            self._log_debug("provider_response_raw", **payload)
            return
        safe_text = _redact_sensitive_text(text, extra_secrets=(self._api_key,))
        if self.log_response == "raw":
            payload["contentRaw"] = safe_text
        else:
            payload["contentPreview"] = safe_text[:2000]
        self._log_debug("provider_response_raw", **payload)


def extract_json_object(text: str) -> Mapping[str, Any]:
    """从模型文本中提取第一个 JSON object。"""
    candidate = _first_json_object_text(text)
    if candidate is None:
        raise ValueError("No JSON object found in model content")
    parsed = json.loads(candidate)
    if not isinstance(parsed, Mapping):
        raise ValueError("Model content JSON must be an object")
    return dict(parsed)


def _message_to_openai(message: ModelMessage) -> dict[str, Any]:
    role = str(message.role).strip()
    if not role:
        raise ProviderResponseError(
            "Model message role must not be empty",
            code="invalid_request",
            safe_summary="Model message role must not be empty",
        )
    result: dict[str, Any] = {"role": role}
    if message.content is not None:
        result["content"] = message.content
    if message.name:
        result["name"] = message.name
    if message.tool_call_id:
        result["tool_call_id"] = message.tool_call_id
    return result


def _tool_to_openai(tool: ModelToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": mutable_mapping(tool.input_schema),
        },
    }


def _parse_tool_calls(raw_tool_calls: Any) -> list[ModelToolCall]:
    if raw_tool_calls is None:
        return []
    if not isinstance(raw_tool_calls, list | tuple):
        raise ProviderResponseError(
            "OpenAI-compatible provider returned invalid tool_calls shape",
            code="provider_response_error",
            safe_summary="OpenAI-compatible provider returned invalid tool_calls shape",
        )
    parsed: list[ModelToolCall] = []
    for index, raw_call in enumerate(raw_tool_calls):
        function = _value(raw_call, "function") or {}
        name = _value(function, "name") or _value(raw_call, "name")
        raw_arguments_value = _value(function, "arguments") or _value(raw_call, "arguments")
        raw_arguments = str(raw_arguments_value if raw_arguments_value is not None else "{}")
        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ProviderResponseError(
                "OpenAI-compatible provider returned invalid tool arguments JSON",
                code="invalid_tool_arguments",
                safe_summary="OpenAI-compatible provider returned invalid tool arguments JSON",
            ) from exc
        if not isinstance(arguments, Mapping):
            raise ProviderResponseError(
                "OpenAI-compatible provider tool arguments must be a JSON object",
                code="invalid_tool_arguments",
                safe_summary="OpenAI-compatible provider tool arguments must be a JSON object",
            )
        parsed.append(
            ModelToolCall(
                id=str(_value(raw_call, "id") or f"tool_call_{index}"),
                name=str(name or ""),
                raw_arguments=raw_arguments,
                arguments=dict(arguments),
            )
        )
    return parsed


def _parse_usage(raw_usage: Any) -> ModelUsage | None:
    if raw_usage is None:
        return None
    return ModelUsage(
        prompt_tokens=_optional_int(_value(raw_usage, "prompt_tokens")),
        completion_tokens=_optional_int(_value(raw_usage, "completion_tokens")),
        total_tokens=_optional_int(_value(raw_usage, "total_tokens")),
    )


def _first_choice(completion: Any) -> Any:
    choices = _value(completion, "choices")
    if not isinstance(choices, list | tuple) or not choices:
        raise ProviderResponseError(
            "OpenAI-compatible provider returned no choices",
            code="provider_response_error",
            safe_summary="OpenAI-compatible provider returned no choices",
        )
    return choices[0]


def _value(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _content_text(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    return str(content)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _completion_request_id(completion: Any) -> str | None:
    request_id = _value(completion, "_request_id") or _value(completion, "request_id")
    return str(request_id) if request_id else None


def _first_json_object_text(text: str) -> str | None:
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


def _read_response_format(value: str | None) -> str:
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


def _read_log_payload(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "none"
    normalized = str(value).strip().lower()
    if normalized in ("none", "off", "disabled", "false", "0"):
        return "none"
    if normalized in ("preview", "raw"):
        return normalized
    raise ProviderConfigurationError(
        "Invalid provider payload log mode: expected none, preview or raw"
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _sdk_error_summary(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:300] if text else type(exc).__name__


def _sanitize_log_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _sanitize_log_value(value)
        for key, value in fields.items()
        if value is not None
    }


def _sanitize_log_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_log_fields(value)
    if isinstance(value, list | tuple):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, str):
        return _redact_sensitive_text(value)
    return value


def _redact_sensitive_text(
    text: str,
    extra_secrets: Sequence[str] = (),
) -> str:
    redacted = text
    for secret in extra_secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    redacted = re.sub(
        r"(?i)(api[_-]?key|authorization|bearer)\s*[:= ]\s*['\"]?[^'\"\s,}]+",
        r"\1=<redacted>",
        redacted,
    )
    return redacted
