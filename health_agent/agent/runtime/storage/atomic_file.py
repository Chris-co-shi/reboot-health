"""安全目录权限与原子文件写入工具。

JSON Store 不能直接对目标文件 `write_text`，否则进程崩溃或并发写入可能留下半截
JSON。本模块使用同目录临时文件、fsync 和 os.replace，保证读者只能看到旧完整文件
或新完整文件。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from agent.runtime.storage.errors import JsonStoreIOError

PRIVATE_DIR_MODE = 0o700
FILE_MODE = 0o600


def ensure_private_directory(path: Path) -> None:
    """创建仅当前用户可访问的目录，并 best-effort 收紧权限到 0700。

    POSIX 平台会遵守 chmod；Windows 或不支持权限位的文件系统上，chmod 失败不影响
    数据正确性，因此只把 mkdir 失败视为 Store IO 错误。
    """

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JsonStoreIOError("Store directory could not be created") from exc
    _best_effort_chmod(path, PRIVATE_DIR_MODE)


def atomic_write_text(target: Path, text: str, *, mode: int = FILE_MODE) -> None:
    """把 UTF-8 文本原子写入目标文件。

    真实写入顺序：
    1. 在目标同目录创建唯一临时文件；
    2. 写入完整 UTF-8 bytes；
    3. flush + fsync 临时文件；
    4. 设置临时文件安全权限；
    5. os.replace 原子替换目标；
    6. best-effort fsync 父目录，尽量持久化 rename 元数据。
    """

    ensure_private_directory(target.parent)
    temp_path: Path | None = None
    fd: int | None = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=str(target.parent),
        )
        temp_path = Path(temp_name)
        _best_effort_fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        _best_effort_chmod(temp_path, mode)
        os.replace(temp_path, target)
        temp_path = None
        _best_effort_chmod(target, mode)
        _best_effort_fsync_directory(target.parent)
    except OSError as exc:
        raise JsonStoreIOError("Store file could not be written atomically") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _best_effort_chmod(path: Path, mode: int) -> None:
    """尽力设置文件或目录权限；权限位不可用时不影响 Store 正确性。"""

    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _best_effort_fchmod(fd: int, mode: int) -> None:
    """尽力在文件描述符层面设置权限，减少 replace 前的权限窗口。"""

    if not hasattr(os, "fchmod"):
        return
    try:
        os.fchmod(fd, mode)
    except OSError:
        pass


def _best_effort_fsync_directory(directory: Path) -> None:
    """尽力 fsync 父目录。

    POSIX 上目录 fd 可以 fsync；部分平台或文件系统不支持目录 fsync，此时不能让
    已成功的 os.replace 变成失败写入，只做 best-effort。
    """

    if os.name == "nt":
        return
    fd: int | None = None
    try:
        fd = os.open(directory, os.O_RDONLY)
        os.fsync(fd)
    except OSError:
        pass
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
