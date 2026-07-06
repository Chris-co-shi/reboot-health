"""记忆摘要预留模块。

摘要只能降低上下文体积，不能把模型推断升级成已确认健康事实。
"""

from __future__ import annotations


def summarize_candidates(texts: list[str]) -> str:
    """生成最小摘要；当前只做确定性拼接，避免引入模型依赖。"""
    return "\n".join(text.strip() for text in texts if text.strip())
