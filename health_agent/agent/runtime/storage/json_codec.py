"""AgentSession 与 PendingAction 的 JSON 序列化合同。

本模块不使用 dataclasses.asdict、pickle、eval 或 Python 类路径，而是显式定义每个
字段的磁盘格式。反序列化严格校验 schema、entity_type、ID、枚举、datetime、消息
结构和 PendingAction arguments_hash，损坏文件不能被当作不存在或被自动修复。
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Mapping

from agent.models import ModelMessage, ModelToolCall
from agent.models.base import mutable_mapping
from agent.runtime.continuation import AgentContinuation
from agent.runtime.pending_action import PendingAction
from agent.runtime.session import AgentSession, AgentSessionStatus
from agent.runtime.storage.errors import (
    JsonStoreDataCorrupted,
    JsonStoreUnsupportedSchema,
)

SCHEMA_VERSION = 1
SESSION_ENTITY_TYPE = "agent_session"
PENDING_ACTION_ENTITY_TYPE = "pending_action"


def safe_entity_key(entity_id: str) -> str:
    """把外部 ID 映射为安全文件名。

    文件名只使用 SHA-256 十六进制文本，不直接拼接用户可控 ID，因此可以抵抗
    `../`、绝对路径、路径分隔符和控制字符。真实 ID 仍保存在 JSON data 内，并在
    get 时与调用方请求 ID 做一致性校验。
    """

    normalized = _require_non_empty_string(entity_id, "entity_id")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def session_to_payload(session: AgentSession) -> dict[str, Any]:
    """把 AgentSession 转成带 schema wrapper 的稳定 JSON object。"""

    return {
        "schema_version": SCHEMA_VERSION,
        "entity_type": SESSION_ENTITY_TYPE,
        "data": {
            "session_id": session.session_id,
            "status": session.status.value,
            "messages": [_message_to_json(message) for message in session.messages],
            "pending_action_id": session.pending_action_id,
            "continuation": (
                _continuation_to_json(session.continuation)
                if session.continuation is not None
                else None
            ),
            "active_run_id": session.active_run_id,
            "version": session.version,
            "created_at": _datetime_to_json(session.created_at),
            "updated_at": _datetime_to_json(session.updated_at),
            "current_skill": session.current_skill,
            "turns": session.turns,
            "pending_confirmations": list(session.pending_confirmations),
            "context_summary": session.context_summary,
            "locale": session.locale,
        },
    }


def session_from_payload(
    payload: Mapping[str, Any],
    *,
    expected_session_id: str | None = None,
) -> AgentSession:
    """从 JSON payload 恢复 AgentSession，并执行严格合同校验。"""

    data = _unwrap_payload(payload, entity_type=SESSION_ENTITY_TYPE)
    _require_fields(
        data,
        {
            "session_id",
            "status",
            "messages",
            "pending_action_id",
            "continuation",
            "active_run_id",
            "version",
            "created_at",
            "updated_at",
            "current_skill",
            "turns",
            "pending_confirmations",
            "context_summary",
            "locale",
        },
    )
    session_id = _require_non_empty_string(data["session_id"], "session_id")
    if expected_session_id is not None and session_id != expected_session_id:
        raise JsonStoreDataCorrupted("Session id does not match requested id")
    try:
        return AgentSession(
            session_id=session_id,
            status=AgentSessionStatus(_require_non_empty_string(data["status"], "status")),
            messages=_messages_from_json(data["messages"]),
            pending_action_id=_optional_string(data["pending_action_id"], "pending_action_id"),
            continuation=(
                _continuation_from_json(data["continuation"])
                if data["continuation"] is not None
                else None
            ),
            active_run_id=_optional_string(data["active_run_id"], "active_run_id"),
            version=_non_negative_int(data["version"], "version"),
            created_at=_datetime_from_json(data["created_at"], "created_at"),
            updated_at=_datetime_from_json(data["updated_at"], "updated_at"),
            current_skill=_optional_string(data["current_skill"], "current_skill"),
            turns=_non_negative_int(data["turns"], "turns"),
            pending_confirmations=_string_list(
                data["pending_confirmations"],
                "pending_confirmations",
            ),
            context_summary=_require_string(data["context_summary"], "context_summary"),
            locale=_require_string(data["locale"], "locale"),
        )
    except ValueError as exc:
        raise JsonStoreDataCorrupted("Session payload violates runtime contract") from exc


def pending_action_to_payload(action: PendingAction) -> dict[str, Any]:
    """把 PendingAction 转成带 schema wrapper 的稳定 JSON object。"""

    return {
        "schema_version": SCHEMA_VERSION,
        "entity_type": PENDING_ACTION_ENTITY_TYPE,
        "data": {
            "action_id": action.action_id,
            "session_id": action.session_id,
            "originating_run_id": action.originating_run_id,
            "tool_call_id": action.tool_call_id,
            "tool_name": action.tool_name,
            "arguments": mutable_mapping(action.arguments),
            "arguments_hash": action.arguments_hash,
            "assistant_message_index": action.assistant_message_index,
            "tool_call_index": action.tool_call_index,
            "summary": action.summary,
            "status": action.status.value,
            "idempotency_key": action.idempotency_key,
            "created_at": _datetime_to_json(action.created_at),
            "updated_at": _datetime_to_json(action.updated_at),
            "expires_at": _datetime_to_json(action.expires_at),
            "version": action.version,
            "result_content": action.result_content,
            "result_error_code": action.result_error_code,
            "resolved_at": (
                _datetime_to_json(action.resolved_at)
                if action.resolved_at is not None
                else None
            ),
            "decision_reason": action.decision_reason,
        },
    }


def pending_action_from_payload(
    payload: Mapping[str, Any],
    *,
    expected_action_id: str | None = None,
) -> PendingAction:
    """从 JSON payload 恢复 PendingAction，并校验 arguments_hash 未被篡改。"""

    data = _unwrap_payload(payload, entity_type=PENDING_ACTION_ENTITY_TYPE)
    _require_fields(
        data,
        {
            "action_id",
            "session_id",
            "originating_run_id",
            "tool_call_id",
            "tool_name",
            "arguments",
            "arguments_hash",
            "assistant_message_index",
            "tool_call_index",
            "summary",
            "status",
            "idempotency_key",
            "created_at",
            "updated_at",
            "expires_at",
            "version",
            "result_content",
            "result_error_code",
            "resolved_at",
            "decision_reason",
        },
    )
    action_id = _require_non_empty_string(data["action_id"], "action_id")
    if expected_action_id is not None and action_id != expected_action_id:
        raise JsonStoreDataCorrupted("PendingAction id does not match requested id")
    try:
        return PendingAction(
            action_id=action_id,
            session_id=_require_non_empty_string(data["session_id"], "session_id"),
            originating_run_id=_require_non_empty_string(
                data["originating_run_id"],
                "originating_run_id",
            ),
            tool_call_id=_require_non_empty_string(data["tool_call_id"], "tool_call_id"),
            tool_name=_require_non_empty_string(data["tool_name"], "tool_name"),
            arguments=_require_mapping(data["arguments"], "arguments"),
            arguments_hash=_require_non_empty_string(data["arguments_hash"], "arguments_hash"),
            assistant_message_index=_non_negative_int(
                data["assistant_message_index"],
                "assistant_message_index",
            ),
            tool_call_index=_non_negative_int(data["tool_call_index"], "tool_call_index"),
            summary=_require_non_empty_string(data["summary"], "summary"),
            status=_require_non_empty_string(data["status"], "status"),
            idempotency_key=_require_non_empty_string(
                data["idempotency_key"],
                "idempotency_key",
            ),
            created_at=_datetime_from_json(data["created_at"], "created_at"),
            updated_at=_datetime_from_json(data["updated_at"], "updated_at"),
            expires_at=_datetime_from_json(data["expires_at"], "expires_at"),
            version=_non_negative_int(data["version"], "version"),
            result_content=_optional_string(data["result_content"], "result_content"),
            result_error_code=_optional_string(
                data["result_error_code"],
                "result_error_code",
            ),
            resolved_at=(
                _datetime_from_json(data["resolved_at"], "resolved_at")
                if data["resolved_at"] is not None
                else None
            ),
            decision_reason=_optional_string(data["decision_reason"], "decision_reason"),
        )
    except ValueError as exc:
        raise JsonStoreDataCorrupted("PendingAction payload violates runtime contract") from exc


def dumps_payload(payload: Mapping[str, Any]) -> str:
    """输出确定性 UTF-8 JSON 文本，不允许 NaN/Infinity。"""

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def loads_payload(text: str) -> Mapping[str, Any]:
    """解析 JSON 文本；语法错误按损坏文件处理。"""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JsonStoreDataCorrupted("Store JSON is not valid") from exc
    if not isinstance(payload, Mapping):
        raise JsonStoreDataCorrupted("Store JSON top-level value must be an object")
    return payload


def _unwrap_payload(payload: Mapping[str, Any], *, entity_type: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise JsonStoreDataCorrupted("Store payload must be an object")
    _require_fields(payload, {"schema_version", "entity_type", "data"})
    if payload["schema_version"] != SCHEMA_VERSION:
        raise JsonStoreUnsupportedSchema("Store schema_version is not supported")
    if payload["entity_type"] != entity_type:
        raise JsonStoreDataCorrupted("Store entity_type does not match")
    data = payload["data"]
    if not isinstance(data, Mapping):
        raise JsonStoreDataCorrupted("Store data must be an object")
    return data


def _message_to_json(message: ModelMessage) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "name": message.name,
        "tool_call_id": message.tool_call_id,
        "tool_calls": [_tool_call_to_json(call) for call in message.tool_calls],
    }


def _messages_from_json(value: Any) -> list[ModelMessage]:
    if not isinstance(value, list):
        raise JsonStoreDataCorrupted("messages must be an array")
    return [_message_from_json(item, index) for index, item in enumerate(value)]


def _message_from_json(value: Any, index: int) -> ModelMessage:
    if not isinstance(value, Mapping):
        raise JsonStoreDataCorrupted(f"messages[{index}] must be an object")
    _require_fields(value, {"role", "content", "name", "tool_call_id", "tool_calls"})
    try:
        return ModelMessage(
            role=_require_non_empty_string(value["role"], "message.role"),
            content=_optional_string(value["content"], "message.content"),
            name=_optional_string(value["name"], "message.name"),
            tool_call_id=_optional_string(value["tool_call_id"], "message.tool_call_id"),
            tool_calls=tuple(_tool_calls_from_json(value["tool_calls"])),
        )
    except ValueError as exc:
        raise JsonStoreDataCorrupted("ModelMessage payload violates model contract") from exc


def _tool_call_to_json(tool_call: ModelToolCall) -> dict[str, Any]:
    return {
        "id": tool_call.id,
        "name": tool_call.name,
        "raw_arguments": tool_call.raw_arguments,
        "arguments": mutable_mapping(tool_call.arguments),
    }


def _tool_calls_from_json(value: Any) -> list[ModelToolCall]:
    if not isinstance(value, list):
        raise JsonStoreDataCorrupted("tool_calls must be an array")
    return [_tool_call_from_json(item, index) for index, item in enumerate(value)]


def _tool_call_from_json(value: Any, index: int) -> ModelToolCall:
    if not isinstance(value, Mapping):
        raise JsonStoreDataCorrupted(f"tool_calls[{index}] must be an object")
    _require_fields(value, {"id", "name", "raw_arguments", "arguments"})
    try:
        return ModelToolCall(
            id=_require_non_empty_string(value["id"], "tool_call.id"),
            name=_require_non_empty_string(value["name"], "tool_call.name"),
            raw_arguments=_require_string(value["raw_arguments"], "tool_call.raw_arguments"),
            arguments=_require_mapping(value["arguments"], "tool_call.arguments"),
        )
    except ValueError as exc:
        raise JsonStoreDataCorrupted("ModelToolCall payload violates model contract") from exc


def _continuation_to_json(continuation: AgentContinuation) -> dict[str, Any]:
    return {
        "originating_run_id": continuation.originating_run_id,
        "assistant_message_index": continuation.assistant_message_index,
        "next_tool_call_index": continuation.next_tool_call_index,
        "model_turns_used": continuation.model_turns_used,
        "tool_calls_used": continuation.tool_calls_used,
        "started_at": _datetime_to_json(continuation.started_at),
        "deadline_at": _datetime_to_json(continuation.deadline_at),
        "remaining_runtime_seconds": continuation.remaining_runtime_seconds,
    }


def _continuation_from_json(value: Any) -> AgentContinuation:
    if not isinstance(value, Mapping):
        raise JsonStoreDataCorrupted("continuation must be an object or null")
    _require_fields(
        value,
        {
            "originating_run_id",
            "assistant_message_index",
            "next_tool_call_index",
            "model_turns_used",
            "tool_calls_used",
            "started_at",
            "deadline_at",
            "remaining_runtime_seconds",
        },
    )
    try:
        return AgentContinuation(
            originating_run_id=_require_non_empty_string(
                value["originating_run_id"],
                "originating_run_id",
            ),
            assistant_message_index=_non_negative_int(
                value["assistant_message_index"],
                "assistant_message_index",
            ),
            next_tool_call_index=_non_negative_int(
                value["next_tool_call_index"],
                "next_tool_call_index",
            ),
            model_turns_used=_non_negative_int(value["model_turns_used"], "model_turns_used"),
            tool_calls_used=_non_negative_int(value["tool_calls_used"], "tool_calls_used"),
            started_at=_datetime_from_json(value["started_at"], "started_at"),
            deadline_at=_datetime_from_json(value["deadline_at"], "deadline_at"),
            remaining_runtime_seconds=(
                _non_negative_number(
                    value["remaining_runtime_seconds"],
                    "remaining_runtime_seconds",
                )
                if value["remaining_runtime_seconds"] is not None
                else None
            ),
        )
    except ValueError as exc:
        raise JsonStoreDataCorrupted("Continuation payload violates runtime contract") from exc


def _datetime_to_json(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise JsonStoreDataCorrupted("datetime value must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _datetime_from_json(value: Any, field_name: str) -> datetime:
    text = _require_non_empty_string(value, field_name)
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise JsonStoreDataCorrupted(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise JsonStoreDataCorrupted(f"{field_name} must be timezone-aware")
    return parsed.astimezone(UTC)


def _require_fields(payload: Mapping[str, Any], fields: set[str]) -> None:
    missing = sorted(field for field in fields if field not in payload)
    if missing:
        raise JsonStoreDataCorrupted("Store payload is missing required fields")


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise JsonStoreDataCorrupted(f"{field_name} must be an object")
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise JsonStoreDataCorrupted(f"{field_name} must be a string")
    return value


def _require_non_empty_string(value: Any, field_name: str) -> str:
    text = _require_string(value, field_name).strip()
    if not text:
        raise JsonStoreDataCorrupted(f"{field_name} must not be empty")
    return text


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name)


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise JsonStoreDataCorrupted(f"{field_name} must be an array")
    result: list[str] = []
    for item in value:
        result.append(_require_string(item, field_name))
    return result


def _non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise JsonStoreDataCorrupted(f"{field_name} must be a non-negative integer")
    return value


def _non_negative_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise JsonStoreDataCorrupted(f"{field_name} must be a non-negative number")
    return float(value)
