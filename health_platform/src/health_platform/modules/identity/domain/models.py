"""Identity 富领域模型。

所属层：Identity / Domain。
职责：保护用户、会话、Token Family、MFA 与删除冷静期不变量。
边界：纯 Python；不负责持久化、HTTP、环境变量或外部 I/O。
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间，避免 naive datetime 混入领域状态。"""
    return datetime.now(UTC)


def new_id() -> UUID:
    """生成不透明 UUID；持久层可在 PostgreSQL 支持后切换原生 UUID v7。"""
    return uuid4()


def normalize_email(value: str) -> str:
    """规范化邮箱登录标识；保留地址语义，不做供应商特有改写。"""
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    if len(normalized) > 320 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise IdentityError("IDENTITY_INVALID_EMAIL", "邮箱格式无效")
    return normalized


def normalize_username(value: str) -> str:
    """使用 NFKC + casefold 建立不区分大小写的稳定登录键。"""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", normalized):
        raise IdentityError("IDENTITY_INVALID_USERNAME", "用户名格式无效")
    return normalized


def hash_secret(value: str, pepper: str = "") -> str:
    """哈希高熵 Token；恒定长度摘要可安全用于数据库和 Redis Key。"""
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


class IdentityError(ValueError):
    """可安全映射为稳定 API 错误码的领域异常。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UserStatus(StrEnum):
    """用户账号状态。"""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DELETION_PENDING = "DELETION_PENDING"
    DELETED = "DELETED"


class SessionStatus(StrEnum):
    """设备会话状态。"""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class TokenFamilyStatus(StrEnum):
    """Refresh Token Family 安全状态。"""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    REPLAY_COMPROMISED = "REPLAY_COMPROMISED"


class Role(StrEnum):
    """第一版单租户 RBAC 角色。"""

    USER = "USER"
    HEALTH_ADVISOR = "HEALTH_ADVISOR"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"

    @property
    def requires_mfa(self) -> bool:
        """说明高权限角色进入管理能力前是否强制 MFA。"""
        return self is not Role.USER


@dataclass
class UserAccount:
    """用户聚合根；保护状态、权限版本和登录锁定不变量。"""

    email: str
    username: str
    display_name: str
    password_hash: str
    id: UUID = field(default_factory=new_id)
    status: UserStatus = UserStatus.PENDING_VERIFICATION
    email_verified_at: datetime | None = None
    permission_version: int = 1
    failed_login_count: int = 0
    locked_until: datetime | None = None
    roles: set[Role] = field(default_factory=lambda: {Role.USER})
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.email = normalize_email(self.email)
        self.username = normalize_username(self.username)
        self.display_name = self.display_name.strip()
        if not self.display_name or len(self.display_name) > 100:
            raise IdentityError("IDENTITY_INVALID_DISPLAY_NAME", "展示名称无效")

    def verify_email(self, now: datetime | None = None) -> None:
        """确认邮箱并激活账号；禁用或删除账号不能被验证动作复活。"""
        if self.status not in {UserStatus.PENDING_VERIFICATION, UserStatus.ACTIVE}:
            raise IdentityError("IDENTITY_USER_NOT_ACTIVE", "账号状态不允许验证邮箱")
        self.email_verified_at = now or utc_now()
        self.status = UserStatus.ACTIVE
        self.updated_at = self.email_verified_at

    def record_login_failure(self, now: datetime | None = None) -> timedelta:
        """应用渐进退避并在连续失败后短期锁定，成功登录不会删除安全审计。"""
        current = now or utc_now()
        self.failed_login_count += 1
        seconds = min(2 ** max(0, self.failed_login_count - 1), 300)
        if self.failed_login_count >= 5:
            self.locked_until = current + timedelta(seconds=seconds)
        self.updated_at = current
        return timedelta(seconds=seconds)

    def record_login_success(self, now: datetime | None = None) -> None:
        """清理活动失败计数，但历史失败仍由 AuditEvent 保存。"""
        self.failed_login_count = 0
        self.locked_until = None
        self.updated_at = now or utc_now()

    def assert_can_login(self, now: datetime | None = None) -> None:
        """拒绝禁用、待删除、已删除或仍处于锁定期的账号。"""
        current = now or utc_now()
        if self.status in {UserStatus.DISABLED, UserStatus.DELETION_PENDING, UserStatus.DELETED}:
            raise IdentityError("IDENTITY_INVALID_CREDENTIALS", "账号或密码错误")
        if self.locked_until and self.locked_until > current:
            raise IdentityError("IDENTITY_TEMPORARILY_LOCKED", "账号暂时锁定")

    def disable(self) -> None:
        """禁用用户并提高权限版本，使缓存中的旧授权立即失效。"""
        if self.status is UserStatus.DELETED:
            raise IdentityError("IDENTITY_INVALID_STATE", "已删除账号不能禁用")
        self.status = UserStatus.DISABLED
        self.permission_version += 1
        self.updated_at = utc_now()


@dataclass
class IdentitySession:
    """一次设备登录会话；每个会话拥有独立 Token Family。"""

    user_id: UUID
    client_id: str
    device_name: str
    client_type: str
    id: UUID = field(default_factory=new_id)
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    last_login_at: datetime = field(default_factory=utc_now)
    last_activity_at: datetime = field(default_factory=utc_now)
    revoked_at: datetime | None = None

    def revoke(self, now: datetime | None = None) -> None:
        """幂等撤销会话；撤销后不得再次活跃。"""
        if self.status is SessionStatus.ACTIVE:
            self.status = SessionStatus.REVOKED
            self.revoked_at = now or utc_now()


@dataclass
class RefreshTokenRecord:
    """Refresh Token 的哈希记录；明文只在签发边界短暂存在。"""

    token_hash: str
    expires_at: datetime
    id: UUID = field(default_factory=new_id)
    issued_at: datetime = field(default_factory=utc_now)
    consumed_at: datetime | None = None
    replaced_by_id: UUID | None = None


@dataclass
class TokenFamily:
    """设备级 Refresh Token 轮换聚合，负责重放检测与整族撤销。"""

    user_id: UUID
    session_id: UUID
    id: UUID = field(default_factory=new_id)
    status: TokenFamilyStatus = TokenFamilyStatus.ACTIVE
    tokens: list[RefreshTokenRecord] = field(default_factory=list)
    revoked_at: datetime | None = None

    def issue_initial(self, token_hash: str, expires_at: datetime) -> RefreshTokenRecord:
        """为新设备签发 Family 的首个 Refresh Token。"""
        if self.tokens:
            raise IdentityError("IDENTITY_TOKEN_FAMILY_INITIALIZED", "Token Family 已初始化")
        record = RefreshTokenRecord(token_hash=token_hash, expires_at=expires_at)
        self.tokens.append(record)
        return record

    def rotate(
        self, presented_hash: str, new_hash: str, expires_at: datetime, now: datetime | None = None
    ) -> RefreshTokenRecord:
        """原子语义消费旧 Token；已消费 Token 再现即判定整族泄露并撤销。"""
        current = now or utc_now()
        if self.status is not TokenFamilyStatus.ACTIVE:
            raise IdentityError("IDENTITY_REFRESH_TOKEN_REVOKED", "Refresh Token 已撤销")
        record = next((item for item in self.tokens if item.token_hash == presented_hash), None)
        if record is None or record.expires_at <= current:
            raise IdentityError("IDENTITY_INVALID_REFRESH_TOKEN", "Refresh Token 无效")
        if record.consumed_at is not None:
            self.status = TokenFamilyStatus.REPLAY_COMPROMISED
            self.revoked_at = current
            raise IdentityError("IDENTITY_REFRESH_TOKEN_REPLAY", "检测到 Refresh Token 重放")
        replacement = RefreshTokenRecord(token_hash=new_hash, expires_at=expires_at)
        record.consumed_at = current
        record.replaced_by_id = replacement.id
        self.tokens.append(replacement)
        return replacement

    def revoke(self, now: datetime | None = None) -> None:
        """撤销整个 Family，使该设备全部 Refresh Token 失效。"""
        if self.status is TokenFamilyStatus.ACTIVE:
            self.status = TokenFamilyStatus.REVOKED
            self.revoked_at = now or utc_now()


@dataclass(frozen=True)
class RecoveryCode:
    """一次性 MFA 恢复码哈希；领域对象永不保存明文。"""

    code_hash: str
    used_at: datetime | None = None

    def consume(self, presented_hash: str, now: datetime | None = None) -> RecoveryCode:
        """恒定时间比较并一次性消费恢复码，阻止重复使用。"""
        if self.used_at is not None or not hmac.compare_digest(self.code_hash, presented_hash):
            raise IdentityError("IDENTITY_INVALID_RECOVERY_CODE", "恢复码无效")
        return RecoveryCode(code_hash=self.code_hash, used_at=now or utc_now())


@dataclass
class AccountDeletionRequest:
    """账号删除冷静期状态；本 Slice 只负责 Identity 与跨模块任务框架。"""

    user_id: UUID
    requested_at: datetime = field(default_factory=utc_now)
    id: UUID = field(default_factory=new_id)
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def ready_at(self) -> datetime:
        """返回固定七天冷静期结束时间。"""
        return self.requested_at + timedelta(days=7)

    def cancel(self, now: datetime | None = None) -> None:
        """仅在开始最终删除前允许用户撤销请求。"""
        if self.completed_at is not None:
            raise IdentityError("IDENTITY_DELETION_ALREADY_COMPLETED", "删除已完成")
        self.cancelled_at = now or utc_now()


def generate_token(byte_length: int = 32) -> str:
    """使用 CSPRNG 生成 URL-safe 高熵不透明 Token。"""
    if byte_length < 32:
        raise ValueError("security tokens require at least 256 bits")
    return secrets.token_urlsafe(byte_length)
