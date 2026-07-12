"""Redis 认证缓存适配器。

Redis 仅保存 Token 哈希键和最小校验结果；任何故障都安全降级为 miss。
"""

import json

from redis import Redis
from redis.exceptions import RedisError


class RedisAuthCache:
    """Redis 短 TTL 缓存；故障不绕过认证，也不使数据库有效会话失效。"""

    def __init__(self, client: Redis) -> None:
        self._client = client

    def get(self, key: str) -> dict[str, object] | None:
        """读取缓存；网络或格式异常统一视为 miss 并由上层回查 PostgreSQL。"""
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw else None
        except (RedisError, json.JSONDecodeError, TypeError):
            return None

    def set(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        """写入有限 TTL，不允许调用方创建永久认证缓存。"""
        try:
            self._client.setex(key, ttl_seconds, json.dumps(value, separators=(",", ":")))
        except RedisError:
            return

    def delete(self, key: str) -> None:
        """尽力失效；数据库撤销仍是权威且不会因 Redis 失败回滚。"""
        try:
            self._client.delete(key)
        except RedisError:
            return
