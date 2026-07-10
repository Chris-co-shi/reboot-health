"""Health Agent 本地入口。

当前入口通过产品 Bootstrap 调用真实 OpenAI-compatible Provider，运行一次
INITIAL_PLANNING 兼容 flow。它不是 HTTP API，也不会连接数据库。
"""

from __future__ import annotations

import json

from agent.bootstrap import create_agent_core_from_env


def main() -> None:
    """执行一次真实 Provider 驱动的兼容 run，并把结果打印为 JSON。"""
    result = create_agent_core_from_env().run(
        "INITIAL_PLANNING",
        {"userText": "想恢复规律训练，先从低强度开始。"},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
