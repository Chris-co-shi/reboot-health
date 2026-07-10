"""Health Agent 非 LLM 配置入口。

LLM 连接配置由 `agent.config` 和产品 Bootstrap 负责读取；本模块保留给
后续非模型运行配置，避免把工具、数据库等策略散落在环境变量中。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthAgentSettings:
    """当前阶段的最小配置对象。"""

    environment: str = "local"
    default_locale: str = "zh-CN"
    max_agent_steps: int = 1


def default_settings() -> HealthAgentSettings:
    """返回本地开发默认配置。"""
    return HealthAgentSettings()
