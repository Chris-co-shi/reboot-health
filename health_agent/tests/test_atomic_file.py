import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent.runtime.storage.atomic_file import (
    FILE_MODE,
    PRIVATE_DIR_MODE,
    atomic_write_text,
    ensure_private_directory,
)
from agent.runtime.storage.errors import JsonStoreIOError
from agent.runtime.storage.file_lock import entity_lock


class AtomicFileTest(unittest.TestCase):
    """原子文件写入 primitives 的基础行为。"""

    def test_atomic_write_replaces_complete_file_with_private_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "entity.json"

            atomic_write_text(target, '{"version":1}')
            atomic_write_text(target, '{"version":2}')

            self.assertEqual(target.read_text(encoding="utf-8"), '{"version":2}')
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), FILE_MODE)

    def test_replace_failure_keeps_old_target_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "entity.json"
            atomic_write_text(target, '{"version":1}')

            with mock.patch(
                "agent.runtime.storage.atomic_file.os.replace",
                side_effect=OSError("replace failed"),
            ):
                with self.assertRaises(JsonStoreIOError):
                    atomic_write_text(target, '{"version":2}')

            self.assertEqual(target.read_text(encoding="utf-8"), '{"version":1}')
            self.assertEqual(list(Path(temp_dir).glob("*.tmp")), [])

    def test_private_directory_is_created_with_best_effort_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir) / "sessions"

            ensure_private_directory(directory)

            self.assertTrue(directory.is_dir())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), PRIVATE_DIR_MODE)


class EntityLockTest(unittest.TestCase):
    """文件锁只验证基本 acquire/release；跨进程竞争在 Store 测试中覆盖。"""

    def test_entity_lock_creates_private_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "entity.lock"

            with entity_lock(lock_path):
                self.assertTrue(lock_path.exists())

            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), FILE_MODE)


if __name__ == "__main__":
    unittest.main()
