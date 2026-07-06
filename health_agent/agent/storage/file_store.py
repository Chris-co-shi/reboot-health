"""文件存储预留模块。

Agent 不允许任意访问文件系统；后续文件能力必须通过受控 Storage/Tool 边界暴露。
"""

from __future__ import annotations


class FileStore:
    """当前阶段不启用的文件存储骨架。"""

    def read(self, key: str) -> bytes:
        """拒绝读取，避免形成任意文件系统能力。"""
        raise NotImplementedError(f"FileStore is not enabled: {key}")
