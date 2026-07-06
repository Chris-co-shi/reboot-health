"""API 依赖预留模块。

API 层后续只能装配 Runtime、Registry 和受控服务，不能绕过 Tool/Domain 边界。
"""

from __future__ import annotations

from agent.runtime.core import AgentCore


def get_agent_core() -> AgentCore:
    """返回默认 AgentCore，用于未来 API 依赖注入。"""
    return AgentCore.default()
