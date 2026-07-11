"""Runtime 本地 JSON 持久化组件。

本包只提供显式选择的本地文件 Store 能力；产品默认路径仍由 Bootstrap 使用
InMemory Store。JSON 文件是明文，适合受控本地环境，不提供静态加密或合规承诺。
"""

from agent.runtime.storage.atomic_file import (
    FILE_MODE,
    PRIVATE_DIR_MODE,
    atomic_write_text,
    ensure_private_directory,
)
from agent.runtime.storage.errors import (
    JsonStoreDataCorrupted,
    JsonStoreError,
    JsonStoreIOError,
    JsonStoreUnsupportedSchema,
)
from agent.runtime.storage.file_lock import entity_lock
from agent.runtime.storage.json_codec import (
    SCHEMA_VERSION,
    SESSION_ENTITY_TYPE,
    PENDING_ACTION_ENTITY_TYPE,
    pending_action_from_payload,
    pending_action_to_payload,
    safe_entity_key,
    session_from_payload,
    session_to_payload,
)
from agent.runtime.storage.json_pending_action_store import (
    JsonFilePendingActionStore,
    JsonPendingActionStoreDataCorrupted,
    JsonPendingActionStoreIOError,
    JsonPendingActionStoreUnsupportedSchema,
)
from agent.runtime.storage.json_session_store import (
    JsonFileSessionStore,
    JsonSessionStoreDataCorrupted,
    JsonSessionStoreIOError,
    JsonSessionStoreUnsupportedSchema,
)

__all__ = [
    "FILE_MODE",
    "PRIVATE_DIR_MODE",
    "JsonStoreDataCorrupted",
    "JsonStoreError",
    "JsonStoreIOError",
    "JsonStoreUnsupportedSchema",
    "JsonFilePendingActionStore",
    "JsonFileSessionStore",
    "JsonPendingActionStoreDataCorrupted",
    "JsonPendingActionStoreIOError",
    "JsonPendingActionStoreUnsupportedSchema",
    "JsonSessionStoreDataCorrupted",
    "JsonSessionStoreIOError",
    "JsonSessionStoreUnsupportedSchema",
    "PENDING_ACTION_ENTITY_TYPE",
    "SCHEMA_VERSION",
    "SESSION_ENTITY_TYPE",
    "atomic_write_text",
    "ensure_private_directory",
    "entity_lock",
    "pending_action_from_payload",
    "pending_action_to_payload",
    "safe_entity_key",
    "session_from_payload",
    "session_to_payload",
]
