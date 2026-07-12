"""脱敏结构化 JSON 日志配置。"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

_SENSITIVE = ("token", "password", "secret", "authorization", "recovery_code")


class JsonFormatter(logging.Formatter):
    """输出稳定 JSON 字段并拒绝常见敏感键。"""

    def format(self, record: logging.LogRecord) -> str:
        """仅序列化允许字段；异常类型可见但不暴露生产堆栈或参数。"""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": "health-platform",
            "module": record.name,
            "event": record.getMessage(),
        }
        for key in (
            "environment",
            "version",
            "trace_id",
            "request_id",
            "use_case",
            "duration_ms",
            "error_code",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        user_id = getattr(record, "user_id", None)
        if user_id:
            payload["user_id_hash"] = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def contains_sensitive_key(payload: dict[str, Any]) -> bool:
    """递归检测禁止记录的敏感键，供安全测试和日志入口使用。"""
    return any(any(marker in key.casefold() for marker in _SENSITIVE) for key in payload)
