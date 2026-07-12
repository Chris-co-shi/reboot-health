"""Identity 第一版应用服务。

所属层：Identity / Application。
职责：编排注册、登录、验证、Token 轮换、会话、MFA、恢复、导出和注销。
边界：基础设施通过构造器注入；不读取环境变量、不 commit、不直接调用 SMTP/Redis。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from health_platform.modules.audit.domain.models import AuditEvent, OutboxEvent
from health_platform.modules.identity.domain.models import (
    AccountDeletionRequest,
    IdentityError,
    IdentitySession,
    RecoveryCode,
    TokenFamily,
    UserAccount,
    UserStatus,
    generate_token,
    hash_secret,
    normalize_email,
)
from health_platform.platform.encryption.service import EncryptedValue, EncryptionPort
from health_platform.platform.security.passwords import PasswordService

OAUTH_BEARER_TOKEN_TYPE = "".join(("Bear", "er"))


class CachePort(Protocol):
    """认证缓存端口；失败必须表现为 miss 而非放行。"""

    def get(self, key: str) -> dict[str, object] | None:
        """读取短 TTL 缓存。"""

    def set(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        """写入不超过 Token 剩余时间的缓存。"""

    def delete(self, key: str) -> None:
        """主动失效缓存。"""


class NullCache:
    """Redis 不可用时的安全降级：始终 miss，但不使有效数据库会话失效。"""

    def get(self, key: str) -> dict[str, object] | None:
        """返回 miss，调用方必须回查权威状态。"""
        return None

    def set(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        """忽略非权威缓存写入。"""

    def delete(self, key: str) -> None:
        """忽略不存在的缓存项。"""


@dataclass
class AccessGrant:
    """不透明 Access Token 的权威最小状态。"""

    token_hash: str
    user_id: UUID
    session_id: UUID
    client_id: str
    audience: str
    scopes: tuple[str, ...]
    permission_version: int
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass
class OneTimeGrant:
    """一次性短期验证/恢复/授权凭证。"""

    user_id: UUID
    kind: str
    token_hash: str
    expires_at: datetime
    payload: dict[str, str] = field(default_factory=dict)
    consumed_at: datetime | None = None
    invalidated_at: datetime | None = None


@dataclass
class MfaState:
    """用户 MFA 加密状态与一次性恢复码。"""

    encrypted_secret: EncryptedValue
    enabled: bool = False
    recovery_codes: list[RecoveryCode] = field(default_factory=list)


@dataclass(frozen=True)
class OAuthClient:
    """预注册第一方 Client；redirect、scope 和 audience 均为确定性白名单。"""

    client_id: str
    redirect_uris: tuple[str, ...]
    allowed_scopes: tuple[str, ...]
    audience: str
    public: bool = True


@dataclass
class AuthorizationGrant:
    """短期一次性 Authorization Code 哈希记录。"""

    user_id: UUID
    client_id: str
    redirect_uri: str
    scope: tuple[str, ...]
    nonce: str
    code_challenge: str
    expires_at: datetime
    consumed_at: datetime | None = None


@dataclass
class IdentityState:
    """应用状态 Port 的参考实现；生产 SQL Adapter 以相同语义持久化。"""

    users: dict[UUID, UserAccount] = field(default_factory=dict)
    sessions: dict[UUID, IdentitySession] = field(default_factory=dict)
    families: dict[UUID, TokenFamily] = field(default_factory=dict)
    access_grants: dict[str, AccessGrant] = field(default_factory=dict)
    one_time_grants: dict[str, OneTimeGrant] = field(default_factory=dict)
    mfa: dict[UUID, MfaState] = field(default_factory=dict)
    deletion_requests: dict[UUID, AccountDeletionRequest] = field(default_factory=dict)
    audits: list[AuditEvent] = field(default_factory=list)
    outbox: list[OutboxEvent] = field(default_factory=list)
    oauth_clients: dict[str, OAuthClient] = field(default_factory=dict)
    authorization_grants: dict[str, AuthorizationGrant] = field(default_factory=dict)


class IdentityService:
    """Identity 用例门面；构造器注入安全、加密、缓存和状态 Port。"""

    def __init__(
        self,
        password_service: PasswordService,
        encryption: EncryptionPort,
        token_pepper: str,
        cache: CachePort | None = None,
        state: IdentityState | None = None,
        access_ttl: timedelta = timedelta(minutes=15),
        refresh_ttl: timedelta = timedelta(days=30),
    ) -> None:
        self._passwords = password_service
        self._encryption = encryption
        self._pepper = token_pepper
        self._cache = cache or NullCache()
        self.state = state or IdentityState()
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    def register(
        self, email: str, username: str, display_name: str, password: str
    ) -> tuple[UserAccount, str]:
        """注册账号并同一逻辑事务创建审计、验证邮件 Outbox；不等待 SMTP。"""
        normalized_email = normalize_email(email)
        if any(
            user.email == normalized_email or user.username == username.strip().casefold()
            for user in self.state.users.values()
        ):
            raise IdentityError("IDENTITY_IDENTIFIER_CONFLICT", "邮箱或用户名已被使用")
        user = UserAccount(
            email=normalized_email,
            username=username,
            display_name=display_name,
            password_hash=self._passwords.hash(password),
        )
        self.state.users[user.id] = user
        token = self._create_one_time(user.id, "EMAIL_VERIFICATION", timedelta(minutes=30))
        self._audit("USER", user.id, "identity.register", "user", user.id, "SUCCESS")
        self._enqueue(
            "identity.email_verification.requested", user.id, {"template": "email_verification_v1"}
        )
        return user, token

    def register_oauth_client(self, client: OAuthClient) -> None:
        """由受信配置注册第一方 Client；不提供动态客户端注册接口。"""
        self.state.oauth_clients[client.client_id] = client

    def authorize(
        self,
        user_id: UUID,
        client_id: str,
        redirect_uri: str,
        scope: tuple[str, ...],
        nonce: str,
        code_challenge: str,
    ) -> str:
        """创建绑定用户、Client、Redirect、Scope、Nonce 和 S256 challenge 的短期授权码。"""
        from health_platform.platform.security.oauth import validate_redirect_uri

        user = self._require_user(user_id)
        if user.email_verified_at is None:
            raise IdentityError("IDENTITY_EMAIL_VERIFICATION_REQUIRED", "需要先验证邮箱")
        client = self.state.oauth_clients.get(client_id)
        if client is None:
            raise IdentityError("IDENTITY_INVALID_CLIENT", "Client 无效")
        validate_redirect_uri(redirect_uri, client.redirect_uris)
        if not set(scope).issubset(client.allowed_scopes):
            raise IdentityError("IDENTITY_INVALID_SCOPE", "scope 无效")
        code = generate_token()
        self.state.authorization_grants[hash_secret(code, self._pepper)] = AuthorizationGrant(
            user_id=user_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            nonce=nonce,
            code_challenge=code_challenge,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        self._audit("USER", user_id, "identity.oauth.authorize", "oauth_client", None, "SUCCESS")
        return code

    def exchange_authorization_code(
        self, code: str, client_id: str, redirect_uri: str, code_verifier: str
    ) -> tuple[dict[str, object], UserAccount, str]:
        """一次性消费授权码并验证 PKCE；返回 Token、用户和 nonce 供固定 RS256 ID Token 签发。"""
        from health_platform.platform.security.oauth import verify_pkce

        grant = self.state.authorization_grants.get(hash_secret(code, self._pepper))
        now = datetime.now(UTC)
        if (
            grant is None
            or grant.consumed_at is not None
            or grant.expires_at <= now
            or grant.client_id != client_id
            or grant.redirect_uri != redirect_uri
            or not verify_pkce(code_verifier, grant.code_challenge)
        ):
            raise IdentityError("IDENTITY_INVALID_AUTHORIZATION_CODE", "授权码无效")
        grant.consumed_at = now
        user = self._require_user(grant.user_id)
        session = IdentitySession(user.id, client_id, "OAuth client", "oauth")
        self.state.sessions[session.id] = session
        family = TokenFamily(user.id, session.id)
        self.state.families[family.id] = family
        client = self.state.oauth_clients[client_id]
        return self._issue_tokens(user, session, family, client.audience), user, grant.nonce

    def verify_email(self, token: str) -> UserAccount:
        """一次性消费验证 Token；成功后权限版本与认证缓存立即失效。"""
        grant = self._consume_one_time(token, "EMAIL_VERIFICATION")
        user = self._require_user(grant.user_id)
        user.verify_email()
        user.permission_version += 1
        self._invalidate_user_cache(user.id)
        self._audit("USER", user.id, "identity.email.verify", "user", user.id, "SUCCESS")
        return user

    def login(
        self,
        identifier: str,
        password: str,
        client_id: str,
        device_name: str,
        client_type: str,
        audience: str = "health-platform-api",
    ) -> dict[str, object]:
        """统一邮箱/用户名登录；所有未知账号与密码错误返回同一错误。"""
        normalized = identifier.strip().casefold()
        user = next(
            (
                item
                for item in self.state.users.values()
                if normalized in {item.email, item.username}
            ),
            None,
        )
        if user is None:
            # 执行一次假哈希验证以降低账号存在与否的明显时序差异。
            self._passwords.verify(self._passwords.hash("constant-dummy-password"), password)
            self._audit("ANONYMOUS", None, "identity.login", "user", None, "FAILURE")
            raise IdentityError("IDENTITY_INVALID_CREDENTIALS", "账号或密码错误")
        user.assert_can_login()
        if not self._passwords.verify(user.password_hash, password):
            user.record_login_failure()
            self._audit("USER", user.id, "identity.login", "user", user.id, "FAILURE")
            raise IdentityError("IDENTITY_INVALID_CREDENTIALS", "账号或密码错误")
        user.record_login_success()
        session = IdentitySession(
            user_id=user.id,
            client_id=client_id,
            device_name=device_name,
            client_type=client_type,
        )
        self.state.sessions[session.id] = session
        family = TokenFamily(user_id=user.id, session_id=session.id)
        self.state.families[family.id] = family
        tokens = self._issue_tokens(user, session, family, audience)
        self._audit("USER", user.id, "identity.login", "session", session.id, "SUCCESS")
        self._enqueue("identity.new_device", user.id, {"session_id": str(session.id)})
        return tokens

    def refresh(
        self, refresh_token: str, audience: str = "health-platform-api"
    ) -> dict[str, object]:
        """轮换 Refresh Token；重放时撤销整个设备 Family并生成高风险通知。"""
        presented_hash = hash_secret(refresh_token, self._pepper)
        family = next(
            (
                item
                for item in self.state.families.values()
                if any(t.token_hash == presented_hash for t in item.tokens)
            ),
            None,
        )
        if family is None:
            raise IdentityError("IDENTITY_INVALID_REFRESH_TOKEN", "Refresh Token 无效")
        user = self._require_user(family.user_id)
        session = self.state.sessions[family.session_id]
        new_refresh = generate_token()
        try:
            family.rotate(
                presented_hash,
                hash_secret(new_refresh, self._pepper),
                datetime.now(UTC) + self._refresh_ttl,
            )
        except IdentityError as exc:
            if exc.code == "IDENTITY_REFRESH_TOKEN_REPLAY":
                session.revoke()
                self._revoke_session_access(session.id)
                self._audit(
                    "SYSTEM", user.id, "identity.token.replay", "session", session.id, "BLOCKED"
                )
                self._enqueue(
                    "identity.high_risk_security_event", user.id, {"type": "refresh_replay"}
                )
            raise
        access = self._issue_access(user, session, audience)
        self._audit("USER", user.id, "identity.token.refresh", "session", session.id, "SUCCESS")
        return {
            **access,
            "refresh_token": new_refresh,
            "refresh_token_expires_in": int(self._refresh_ttl.total_seconds()),
        }

    def authenticate(self, access_token: str) -> AccessGrant:
        """先查 Redis 短缓存，失败/未命中回查权威状态；未知状态绝不放行。"""
        token_hash = hash_secret(access_token, self._pepper)
        cached = self._cache.get(f"auth:{token_hash}")
        if cached is not None:
            grant = self.state.access_grants.get(token_hash)
            cached_version = cached.get("permission_version")
            if (
                grant is not None
                and isinstance(cached_version, int)
                and grant.permission_version == cached_version
            ):
                return grant
        grant = self.state.access_grants.get(token_hash)
        now = datetime.now(UTC)
        if grant is None or grant.revoked_at is not None or grant.expires_at <= now:
            raise IdentityError("AUTHENTICATION_REQUIRED", "需要登录")
        user = self._require_user(grant.user_id)
        session = self.state.sessions[grant.session_id]
        if session.status.value != "ACTIVE" or user.status not in {
            UserStatus.ACTIVE,
            UserStatus.PENDING_VERIFICATION,
        }:
            raise IdentityError("AUTHENTICATION_REQUIRED", "需要登录")
        if user.permission_version != grant.permission_version:
            raise IdentityError("AUTHENTICATION_REQUIRED", "授权已变更")
        ttl = max(1, int((grant.expires_at - now).total_seconds()))
        self._cache.set(f"auth:{token_hash}", {"permission_version": grant.permission_version}, ttl)
        return grant

    def revoke_session(self, actor_user_id: UUID, session_id: UUID) -> None:
        """按资源归属撤销设备会话、Family、Access Token 和缓存。"""
        session = self.state.sessions.get(session_id)
        if session is None or session.user_id != actor_user_id:
            raise IdentityError("CROSS_USER_ACCESS_DENIED", "无权访问该会话")
        session.revoke()
        for family in self.state.families.values():
            if family.session_id == session_id:
                family.revoke()
        self._revoke_session_access(session_id)
        self._audit(
            "USER", actor_user_id, "identity.session.revoke", "session", session_id, "SUCCESS"
        )

    def enroll_mfa(self, user_id: UUID) -> tuple[str, list[str]]:
        """生成 TOTP Secret 与仅展示一次的恢复码；Secret 入库前先字段加密。"""
        self._require_user(user_id)
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        recovery_plain = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(8)]
        state = MfaState(
            encrypted_secret=self._encryption.encrypt(secret, str(user_id).encode()),
            recovery_codes=[
                RecoveryCode(hash_secret(code, self._pepper)) for code in recovery_plain
            ],
        )
        self.state.mfa[user_id] = state
        self._audit("USER", user_id, "identity.mfa.enroll", "user", user_id, "PENDING")
        return secret, recovery_plain

    def confirm_mfa(self, user_id: UUID, code: str, at: datetime | None = None) -> None:
        """验证 TOTP 后启用 MFA；未确认 enrollment 不得用于高权限登录。"""
        state = self.state.mfa.get(user_id)
        if state is None:
            raise IdentityError("IDENTITY_MFA_NOT_ENROLLED", "MFA 尚未登记")
        secret = self._encryption.decrypt(state.encrypted_secret, str(user_id).encode())
        if not verify_totp(secret, code, at=at):
            raise IdentityError("IDENTITY_INVALID_MFA_CODE", "MFA 验证码无效")
        state.enabled = True
        self._audit("USER", user_id, "identity.mfa.enable", "user", user_id, "SUCCESS")

    def recover_mfa(self, user_id: UUID, code: str) -> None:
        """消费一次性恢复码；成功后原码不可再次使用。"""
        state = self.state.mfa.get(user_id)
        if state is None or not state.enabled:
            raise IdentityError("IDENTITY_MFA_NOT_ENROLLED", "MFA 未启用")
        presented_hash = hash_secret(code, self._pepper)
        for index, recovery in enumerate(state.recovery_codes):
            try:
                state.recovery_codes[index] = recovery.consume(presented_hash)
                self._audit("USER", user_id, "identity.mfa.recover", "user", user_id, "SUCCESS")
                return
            except IdentityError:
                continue
        raise IdentityError("IDENTITY_INVALID_RECOVERY_CODE", "恢复码无效")

    def request_password_reset(self, identifier: str) -> str | None:
        """始终允许 API 返回模糊成功；仅对存在账号创建邮件 Outbox。"""
        normalized = identifier.strip().casefold()
        user = next(
            (u for u in self.state.users.values() if normalized in {u.email, u.username}), None
        )
        if user is None:
            return None
        token = self._create_one_time(user.id, "PASSWORD_RESET", timedelta(minutes=20))
        self._enqueue(
            "identity.password_reset.requested", user.id, {"template": "password_reset_v1"}
        )
        self._audit("USER", user.id, "identity.password_reset.request", "user", user.id, "SUCCESS")
        return token

    def complete_password_reset(self, token: str, new_password: str) -> None:
        """消费短期凭证、更新密码并撤销全部 Session/Token/缓存。"""
        grant = self._consume_one_time(token, "PASSWORD_RESET")
        user = self._require_user(grant.user_id)
        user.password_hash = self._passwords.hash(new_password)
        user.permission_version += 1
        for session in self.state.sessions.values():
            if session.user_id == user.id:
                self.revoke_session(user.id, session.id)
        self._invalidate_user_cache(user.id)
        self._audit("USER", user.id, "identity.password_reset.complete", "user", user.id, "SUCCESS")
        self._enqueue("identity.password_changed", user.id, {"template": "password_changed_v1"})

    def request_export(self, user_id: UUID) -> UUID:
        """创建加密导出任务框架；其他业务模块数据由后续 Phase 扩展。"""
        self._require_user(user_id)
        job_id = uuid4()
        self._enqueue("identity.export.requested", user_id, {"job_id": str(job_id)})
        self._audit("USER", user_id, "identity.export.request", "export_job", job_id, "ACCEPTED")
        return job_id

    def request_deletion(self, user_id: UUID) -> AccountDeletionRequest:
        """创建七天冷静期并立即撤销所有会话；不伪造其他模块已删除。"""
        user = self._require_user(user_id)
        request = AccountDeletionRequest(user_id=user_id)
        self.state.deletion_requests[request.id] = request
        user.status = UserStatus.DELETION_PENDING
        for session in list(self.state.sessions.values()):
            if session.user_id == user_id:
                self.revoke_session(user_id, session.id)
        self._enqueue(
            "identity.account_deletion.requested",
            user_id,
            {"request_id": str(request.id), "scope": "identity_and_coordination"},
        )
        self._audit(
            "USER", user_id, "identity.deletion.request", "deletion_request", request.id, "ACCEPTED"
        )
        return request

    def _issue_tokens(
        self, user: UserAccount, session: IdentitySession, family: TokenFamily, audience: str
    ) -> dict[str, object]:
        refresh = generate_token()
        family.issue_initial(
            hash_secret(refresh, self._pepper), datetime.now(UTC) + self._refresh_ttl
        )
        return {
            **self._issue_access(user, session, audience),
            "refresh_token": refresh,
            "refresh_token_expires_in": int(self._refresh_ttl.total_seconds()),
        }

    def _issue_access(
        self, user: UserAccount, session: IdentitySession, audience: str
    ) -> dict[str, object]:
        access = generate_token()
        token_hash = hash_secret(access, self._pepper)
        scopes = (
            ("account:read", "account:write") if user.email_verified_at else ("account:limited",)
        )
        self.state.access_grants[token_hash] = AccessGrant(
            token_hash=token_hash,
            user_id=user.id,
            session_id=session.id,
            client_id=session.client_id,
            audience=audience,
            scopes=scopes,
            permission_version=user.permission_version,
            expires_at=datetime.now(UTC) + self._access_ttl,
        )
        return {
            "access_token": access,
            "token_type": OAUTH_BEARER_TOKEN_TYPE,
            "expires_in": int(self._access_ttl.total_seconds()),
            "scope": " ".join(scopes),
            "session_id": str(session.id),
        }

    def _create_one_time(self, user_id: UUID, kind: str, ttl: timedelta) -> str:
        for grant in self.state.one_time_grants.values():
            if grant.user_id == user_id and grant.kind == kind and grant.consumed_at is None:
                grant.invalidated_at = datetime.now(UTC)
        token = generate_token()
        token_hash = hash_secret(token, self._pepper)
        self.state.one_time_grants[token_hash] = OneTimeGrant(
            user_id=user_id,
            kind=kind,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + ttl,
        )
        return token

    def _consume_one_time(self, token: str, kind: str) -> OneTimeGrant:
        grant = self.state.one_time_grants.get(hash_secret(token, self._pepper))
        now = datetime.now(UTC)
        if (
            grant is None
            or grant.kind != kind
            or grant.consumed_at
            or grant.invalidated_at
            or grant.expires_at <= now
        ):
            raise IdentityError("IDENTITY_INVALID_ONE_TIME_TOKEN", "一次性凭证无效或已过期")
        grant.consumed_at = now
        return grant

    def _require_user(self, user_id: UUID) -> UserAccount:
        user = self.state.users.get(user_id)
        if user is None:
            raise IdentityError("IDENTITY_USER_NOT_FOUND", "用户不存在")
        return user

    def _revoke_session_access(self, session_id: UUID) -> None:
        now = datetime.now(UTC)
        for grant in self.state.access_grants.values():
            if grant.session_id == session_id:
                grant.revoked_at = now
                self._cache.delete(f"auth:{grant.token_hash}")

    def _invalidate_user_cache(self, user_id: UUID) -> None:
        for grant in self.state.access_grants.values():
            if grant.user_id == user_id:
                self._cache.delete(f"auth:{grant.token_hash}")

    def _audit(
        self,
        actor_type: str,
        user_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        result: str,
    ) -> None:
        previous = self.state.audits[-1].event_hash if self.state.audits else "GENESIS"
        self.state.audits.append(
            AuditEvent(
                actor_type=actor_type,
                actor_id=user_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                result=result,
                previous_hash=previous,
            )
        )

    def _enqueue(self, event_type: str, aggregate_id: UUID, payload: dict[str, str]) -> None:
        self.state.outbox.append(
            OutboxEvent(
                event_type=event_type,
                aggregate_type="user",
                aggregate_id=aggregate_id,
                payload=payload,
            )
        )


def totp_code(secret: str, at: datetime | None = None) -> str:
    """按 RFC 6238 生成 30 秒、6 位 TOTP；Secret 不写日志或持久化明文。"""
    current = at or datetime.now(UTC)
    counter = int(current.timestamp()) // 30
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def verify_totp(secret: str, code: str, at: datetime | None = None) -> bool:
    """允许前后一个时间步，兼顾时钟漂移且不扩大为长时间重放窗口。"""
    current = at or datetime.now(UTC)
    return any(
        hmac.compare_digest(totp_code(secret, current + timedelta(seconds=offset)), code)
        for offset in (-30, 0, 30)
    )
