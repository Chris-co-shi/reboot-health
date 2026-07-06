"""Agent Loop 预留模块。

后续 Agent Loop 必须使用有限步数、有限工具调用、超时和取消边界。当前阶段不实现
自治循环，避免把单次 Skill 调用误描述成完整 Harness。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoopLimits:
    """Agent Loop 的安全上限配置。"""

    max_steps: int = 1
    max_tool_calls: int = 0
    timeout_seconds: float = 30.0
