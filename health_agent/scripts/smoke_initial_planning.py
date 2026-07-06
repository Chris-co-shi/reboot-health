"""本地 INITIAL_PLANNING smoke 脚本。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.runtime.core import AgentCore


def main() -> None:
    """运行一次 MockProvider 首轮规划。"""
    result = AgentCore.default().run(
        "INITIAL_PLANNING",
        {
            "userText": "体能差，游泳容易呛水，血压有点高，想从低强度恢复训练。",
            "today": "2026-07-06",
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
