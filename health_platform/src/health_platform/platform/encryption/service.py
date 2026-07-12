"""版本化信封字段加密。

所属层：Platform / Encryption。
职责：AES-256-GCM 加解密、current/historical 密钥选择与 Secret 文件加载。
边界：不保存密钥到数据库、日志或镜像，不承担业务 Secret 生命周期。
"""

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class EncryptedValue:
    """可持久化的密文信封，不包含明文或主密钥。"""

    ciphertext: str
    nonce: str
    key_version: str
    algorithm: str = "AES-256-GCM"


class KeyManagementPort(Protocol):
    """提供 current 加密密钥和 historical 解密密钥的最小端口。"""

    def current(self) -> tuple[str, bytes]:
        """返回当前加密版本与 256-bit key。"""

    def by_version(self, version: str) -> bytes:
        """返回指定版本的仅解密密钥。"""


class EncryptionPort(Protocol):
    """高敏感字段加解密端口。"""

    def encrypt(self, plaintext: str, associated_data: bytes = b"") -> EncryptedValue:
        """加密新数据。"""

    def decrypt(self, value: EncryptedValue, associated_data: bytes = b"") -> str:
        """按密钥版本解密历史数据。"""


class FileKeyManagementAdapter:
    """从只读 Kubernetes Secret JSON 文件加载版本化密钥的适配器。"""

    def __init__(self, path: str) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self._current_version = str(payload["current_version"])
        self._keys = {
            str(version): base64.b64decode(encoded) for version, encoded in payload["keys"].items()
        }
        if any(len(key) != 32 for key in self._keys.values()):
            raise ValueError("encryption keys must be 256 bit")

    def current(self) -> tuple[str, bytes]:
        """返回 current 版本；只有该版本用于新数据加密。"""
        return self._current_version, self._keys[self._current_version]

    def by_version(self, version: str) -> bytes:
        """返回历史密钥用于解密，未知版本 fail-closed。"""
        return self._keys[version]


class StaticKeyManagementAdapter:
    """仅供确定性测试/本地开发的内存密钥适配器。"""

    def __init__(self, current_version: str, keys: dict[str, bytes]) -> None:
        self._current_version = current_version
        self._keys = dict(keys)

    def current(self) -> tuple[str, bytes]:
        """返回当前测试密钥。"""
        return self._current_version, self._keys[self._current_version]

    def by_version(self, version: str) -> bytes:
        """返回版本化测试密钥。"""
        return self._keys[version]


class AesGcmEncryptionService:
    """使用随机 nonce 和版本化 key 的 AES-GCM 字段加密实现。"""

    def __init__(self, keys: KeyManagementPort) -> None:
        self._keys = keys

    def encrypt(self, plaintext: str, associated_data: bytes = b"") -> EncryptedValue:
        """用 current key 加密；随机 96-bit nonce 保证同一明文密文不同。"""
        version, key = self._keys.current()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), associated_data)
        return EncryptedValue(
            ciphertext=base64.b64encode(ciphertext).decode(),
            nonce=base64.b64encode(nonce).decode(),
            key_version=version,
        )

    def decrypt(self, value: EncryptedValue, associated_data: bytes = b"") -> str:
        """按信封版本选 historical key；认证失败时不返回部分明文。"""
        key = self._keys.by_version(value.key_version)
        plaintext = AESGCM(key).decrypt(
            base64.b64decode(value.nonce),
            base64.b64decode(value.ciphertext),
            associated_data,
        )
        return plaintext.decode()
