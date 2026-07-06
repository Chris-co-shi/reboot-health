"""Health Agent 非敏感配置入口。

`.env` 只应放 secrets。后续非敏感运行配置会收敛到本模块或独立 config 文件，避免
把模型、工具、数据库等策略散落在环境变量中。
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
