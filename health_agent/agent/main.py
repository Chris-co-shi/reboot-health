"""Health Agent 本地入口。

当前入口只运行 MockProvider 驱动的 INITIAL_PLANNING smoke flow，便于 Docker 或
命令行快速验证包结构可导入。它不是 HTTP API，也不会连接真实模型或数据库。
"""

from __future__ import annotations

import json

from agent.runtime.core import AgentCore


def main() -> None:
    """执行一次最小 smoke run，并把结果打印为 JSON。"""
    result = AgentCore.default().run(
        "INITIAL_PLANNING",
        {"userText": "想恢复规律训练，先从低强度开始。"},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
