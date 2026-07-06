"""持久化入口预留模块。

Repository 才能访问数据库；Agent Loop、LLM 和 Prompt 不能直接访问数据库。当前阶段
不连接 PostgreSQL、Redis 或任何外部存储。
"""

from __future__ import annotations


class DatabaseNotConfiguredError(RuntimeError):
    """当前阶段未配置数据库访问。"""
