"""跨进程 advisory file lock。

threading.RLock 只能保护当前进程，JSON Store 的 CAS 需要跨进程互斥。本模块为每个
实体文件提供一把独立锁：同一个 Session ID 或 PendingAction ID 会映射到同一个
`.lock` 文件，不同实体互不阻塞。
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from agent.runtime.storage.atomic_file import FILE_MODE, ensure_private_directory
from agent.runtime.storage.errors import JsonStoreIOError


@contextmanager
def entity_lock(lock_path: Path) -> Iterator[None]:
    """获取实体级跨进程锁，并在异常路径可靠释放。

    锁文件只用于 advisory lock，不保存业务数据。调用方必须保证锁内只做磁盘 Store
    读取、版本比较和原子写入，不在锁内调用模型、工具 handler 或等待用户确认。
    """

    ensure_private_directory(lock_path.parent)
    fd: int | None = None
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, FILE_MODE)
        _best_effort_chmod(lock_path)
        _lock_fd(fd)
        try:
            yield
        finally:
            _unlock_fd(fd)
    except OSError as exc:
        raise JsonStoreIOError("Store lock could not be acquired") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _lock_fd(fd: int) -> None:
    """按平台获取独占 advisory lock。"""

    if os.name == "nt":
        import msvcrt

        # Windows locking 需要对文件范围加锁；锁文件不存业务数据，固定锁 1 字节即可。
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            os.write(fd, b"\0")
        except OSError:
            pass
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        return

    import fcntl

    fcntl.flock(fd, fcntl.LOCK_EX)


def _unlock_fd(fd: int) -> None:
    """释放平台对应的 advisory lock。"""

    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


def _best_effort_chmod(path: Path) -> None:
    """锁文件权限也收紧到 0600；不支持 chmod 时忽略。"""

    try:
        os.chmod(path, FILE_MODE)
    except OSError:
        pass
