"""JSON Store 内部错误类型。

这些错误由 storage 子包内部使用。具体 Store Adapter 会在对外方法中把它们转换
成 SessionStoreError 或 PendingActionStoreError 的子类，保持现有 Store Port 风格。
错误消息只描述原因，不包含完整磁盘路径、JSON payload 或敏感内容。
"""

from __future__ import annotations


class JsonStoreError(RuntimeError):
    """JSON Store 基础错误。"""


class JsonStoreDataCorrupted(JsonStoreError):
    """持久化文件存在但内容不符合当前合同。"""


class JsonStoreUnsupportedSchema(JsonStoreDataCorrupted):
    """持久化文件使用了当前代码不支持的 schema_version。"""


class JsonStoreIOError(JsonStoreError):
    """文件系统读写、权限或锁相关错误。"""
