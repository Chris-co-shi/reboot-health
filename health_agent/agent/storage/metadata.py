"""存储元数据定义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoredObjectMetadata:
    """受控存储对象的最小元数据。"""

    key: str
    content_type: str
    size_bytes: int
