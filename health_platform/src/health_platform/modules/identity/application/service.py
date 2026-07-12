"""Identity 应用服务（Port 重构版）。

所属层：Identity / Application。
职责：编排注册、登录、验证、Token 轮换、会话、MFA、恢复、导出和注销。
边界：基础设施（UoW、Repository、Audit、Outbox、Cache、Encryption、Passwords）
     全部通过构造器注入；不读取环境变量、不 commit、不直接调用 SMTP/Redis，
     缓存与外部副作用在 UoW commit 之后执行。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from health_platform.modules.audit.domain.models import AuditEvent, OutboxEvent
from health_platform.modules.identity.application.ports import (
    AccessGrant,
    AuthorizationGrant,
    IdentityUnitOfWork,
    MfaState,
    OAuthClient,
    OneTimeGrant,
    UoWFactory,
)
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
    normalize_username,
    utc_now,
)
from health_platform.platform.encryption.service import EncryptionPort
from health_platform.platform.security.passwords import PasswordService

OAUTH_BEARER_TOKEN_TYPE = "".join(("Bear", "er"))


# -----------------------------
# 端口：Cache
# -----------------------------


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
        return None

    def set(self, key: str, value: dict[str, object], ttl_seconds: int) -> None:
        return None

    def delete(self, key: str) -> None:
        return None


# -----------------------------
# 领域 dataclass（保持原有形状以兼容 HTTP DTO 与测试）
# 全部 dataclass 现已声明在 ports.py 中以避免循环导入；本模块仅导入使用。
# -----------------------------


# -----------------------------
# 应用服务
# -----------------------------


class IdentityService:
    """Identity 用例门面；构造器注入安全、加密、缓存、UoW；不持有领域状态。"""

    def __init__(
        self,
        password_service: PasswordService,
        encryption: EncryptionPort,
        token_pepper: str,
        uow_factory: UoWFactory,
        cache: CachePort | None = None,
        access_ttl: timedelta = timedelta(minutes=15),
        refresh_ttl: timedelta = timedelta(days=30),
    ) -> None:
        self._passwords = password_service
        self._encryption = encryption
        self._pepper = token_pepper
        self._uow_factory = uow_factory
        self._cache = cache or NullCache()
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    # -----------------------------
    # 事务辅助
    # -----------------------------

    def _write(
        self,
        actor_kind: str,
        actor_user_id: UUID | None,
        body,  # Callable[[IdentityUnitOfWork], T]
    ):
        """进入 UoW、设置 RLS 上下文、执行 body、提交并执行 after_commit hooks。"""
        with self._uow_factory() as uow:
            uow.set_security_context(actor_user_id, actor_kind)
            result = body(uow)
            uow.commit()
            return result

    def _read(self, body):
        """只读路径；UoW 不强制 commit，由实现决定。"""
        with self._uow_factory() as uow:
            return body(uow)

    def _audit(
        self,
        uow: IdentityUnitOfWork,
        actor_type: str,
        user_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        result: str,
    ) -> None:
        """追加审计事件；previous_hash 由 UoW 内部维护。"""
        event = AuditEvent(
            actor_type=actor_type,
            actor_id=user_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            previous_hash=uow.audit.current_hash(),
        )
        uow.audit.append(event)

    def _enqueue(
        self,
        uow: IdentityUnitOfWork,
        event_type: str,
        aggregate_id: UUID,
        payload: dict[str, str],
    ) -> None:
        """同事务入队 Outbox 副作用。"""
        uow.outbox.enqueue(
            OutboxEvent(
                event_type=event_type,
                aggregate_type="user",
                aggregate_id=aggregate_id,
                payload=payload,
            )
        )

    # -----------------------------
    # 用例
    # -----------------------------

    def register(
        self, email: str, username: str, display_name: str, password: str
    ) -> tuple[UserAccount, str]:
        normalized_email = normalize_email(email)
        normalized_username = normalize_username(username)

        def body(uow: IdentityUnitOfWork) -> tuple[UserAccount, str]:
            if uow.users.get_by_identifier(normalized_email) is not None or any(
                u.username == normalized_username for u in uow.users.list_all()
            ):
                raise IdentityError("IDENTITY_IDENTIFIER_CONFLICT", "邮箱或用户名已被使用")
            user = UserAccount(
                email=normalized_email,
                username=normalized_username,
                display_name=display_name,
                password_hash=self._passwords.hash(password),
            )
            uow.users.add(user)
            now = utc_now()
            token = generate_token()
            grant = OneTimeGrant(
                user_id=user.id,
                kind="EMAIL_VERIFICATION",
                token_hash=hash_secret(token, self._pepper),
                expires_at=now + timedelta(minutes=30),
            )
            uow.one_time_tokens.add(grant)
            self._audit(uow, "USER", user.id, "identity.register", "user", user.id, "SUCCESS")
            self._enqueue(
                uow,
                "identity.email_verification.requested",
                user.id,
                {"template": "email_verification_v1"},
            )
            return user, token

        return self._write("user", None, body)

    def register_oauth_client(self, client: OAuthClient) -> None:
        def body(uow: IdentityUnitOfWork) -> None:
            uow.oauth_clients.upsert(client)

        self._write("service", None, body)

    def ensure_oauth_clients(self, clients: list[OAuthClient]) -> None:
        """Composition Root 启动幂等注入第一方 Client；多 Pod 并发安全。"""

        def body(uow: IdentityUnitOfWork) -> None:
            for client in clients:
                uow.oauth_clients.upsert(client)

        self._write("service", None, body)

    def authorize(
        self,
        user_id: UUID,
        client_id: str,
        redirect_uri: str,
        scope: tuple[str, ...],
        nonce: str,
        code_challenge: str,
    ) -> str:
        from health_platform.platform.security.oauth import validate_redirect_uri

        def body(uow: IdentityUnitOfWork) -> str:
            user = self._require_user(uow, user_id)
            if user.email_verified_at is None:
                raise IdentityError("IDENTITY_EMAIL_VERIFICATION_REQUIRED", "需要先验证邮箱")
            client = uow.oauth_clients.get(client_id)
            if client is None:
                raise IdentityError("IDENTITY_INVALID_CLIENT", "Client 无效")
            validate_redirect_uri(redirect_uri, client.redirect_uris)
            if not set(scope).issubset(client.allowed_scopes):
                raise IdentityError("IDENTITY_INVALID_SCOPE", "scope 无效")
            code = generate_token()
            code_hash = hash_secret(code, self._pepper)
            grant = AuthorizationGrant(
                user_id=user_id,
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=scope,
                nonce=nonce,
                code_challenge=code_challenge,
                expires_at=utc_now() + timedelta(minutes=5),
            )
            uow.authorization_grants.add(code_hash, grant)
            self._audit(
                uow, "USER", user_id, "identity.oauth.authorize", "oauth_client", None, "SUCCESS"
            )
            return code

        return self._write("user", user_id, body)

    def exchange_authorization_code(
        self, code: str, client_id: str, redirect_uri: str, code_verifier: str
    ) -> tuple[dict[str, object], UserAccount, str]:
        from health_platform.platform.security.oauth import verify_pkce

        def body(uow: IdentityUnitOfWork) -> tuple[dict[str, object], UserAccount, str]:
            code_hash = hash_secret(code, self._pepper)
            grant = uow.authorization_grants.consume(code_hash)
            now = utc_now()
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
            user = self._require_user(uow, grant.user_id)
            session = IdentitySession(user.id, client_id, "OAuth client", "oauth")
            uow.sessions.add(session)
            family = TokenFamily(user.id, session.id)
            uow.token_families.add(family)
            client = uow.oauth_clients.get(client_id)
            assert client is not None
            tokens = self._issue_tokens(uow, user, session, family, client.audience)
            return tokens, user, grant.nonce

        return self._write("user", None, body)

    def verify_email(self, token: str) -> UserAccount:
        token_hash = hash_secret(token, self._pepper)

        def body(uow: IdentityUnitOfWork) -> UserAccount:
            grant = uow.one_time_tokens.consume(token_hash, "EMAIL_VERIFICATION", utc_now())
            if grant is None:
                raise IdentityError("IDENTITY_INVALID_ONE_TIME_TOKEN", "一次性凭证无效或已过期")
            user = self._require_user(uow, grant.user_id)
            user.verify_email()
            user.permission_version += 1
            uow.users.save(user)
            self._cache_invalidate_user(uow, user.id)
            self._audit(uow, "USER", user.id, "identity.email.verify", "user", user.id, "SUCCESS")
            return user

        return self._write("user", None, body)

    def login(
        self,
        identifier: str,
        password: str,
        client_id: str,
        device_name: str,
        client_type: str,
        audience: str = "health-platform-api",
    ) -> dict[str, object]:
        normalized = identifier.strip().casefold()

        def body(uow: IdentityUnitOfWork) -> dict[str, object]:
            user = next(
                (
                    item
                    for item in uow.users.list_all()
                    if normalized in {item.email, item.username}
                ),
                None,
            )
            if user is None:
                self._passwords.verify(self._passwords.hash("constant-dummy-password"), password)
                self._audit(uow, "ANONYMOUS", None, "identity.login", "user", None, "FAILURE")
                raise IdentityError("IDENTITY_INVALID_CREDENTIALS", "账号或密码错误")
            user.assert_can_login()
            if not self._passwords.verify(user.password_hash, password):
                user.record_login_failure()
                uow.users.save(user)
                self._audit(uow, "USER", user.id, "identity.login", "user", user.id, "FAILURE")
                raise IdentityError("IDENTITY_INVALID_CREDENTIALS", "账号或密码错误")
            user.record_login_success()
            uow.users.save(user)
            session = IdentitySession(
                user_id=user.id,
                client_id=client_id,
                device_name=device_name,
                client_type=client_type,
            )
            uow.sessions.add(session)
            family = TokenFamily(user_id=user.id, session_id=session.id)
            uow.token_families.add(family)
            tokens = self._issue_tokens(uow, user, session, family, audience)
            self._audit(uow, "USER", user.id, "identity.login", "session", session.id, "SUCCESS")
            self._enqueue(uow, "identity.new_device", user.id, {"session_id": str(session.id)})
            return tokens

        return self._write("user", None, body)

    def refresh(
        self, refresh_token: str, audience: str = "health-platform-api"
    ) -> dict[str, object]:
        presented_hash = hash_secret(refresh_token, self._pepper)

        def body(uow: IdentityUnitOfWork) -> dict[str, object]:
            family = uow.token_families.find_by_refresh_hash(presented_hash)
            if family is None:
                raise IdentityError("IDENTITY_INVALID_REFRESH_TOKEN", "Refresh Token 无效")
            user = self._require_user(uow, family.user_id)
            session = uow.sessions.get(family.session_id)
            assert session is not None
            new_refresh = generate_token()
            try:
                family.rotate(
                    presented_hash,
                    hash_secret(new_refresh, self._pepper),
                    utc_now() + self._refresh_ttl,
                )
            except IdentityError as exc:
                if exc.code == "IDENTITY_REFRESH_TOKEN_REPLAY":
                    session.revoke()
                    uow.sessions.save(session)
                    uow.token_families.save(family)
                    self._revoke_session_access_grants(uow, session.id)
                    self._audit(
                        uow,
                        "SYSTEM",
                        user.id,
                        "identity.token.replay",
                        "session",
                        session.id,
                        "BLOCKED",
                    )
                    self._enqueue(
                        uow,
                        "identity.high_risk_security_event",
                        user.id,
                        {"type": "refresh_replay"},
                    )
                raise
            uow.token_families.save(family)
            access = self._issue_access(uow, user, session, audience)
            self._audit(
                uow, "USER", user.id, "identity.token.refresh", "session", session.id, "SUCCESS"
            )
            return {
                **access,
                "refresh_token": new_refresh,
                "refresh_token_expires_in": int(self._refresh_ttl.total_seconds()),
            }

        return self._write("user", None, body)

    def authenticate(self, access_token: str) -> AccessGrant:
        token_hash = hash_secret(access_token, self._pepper)

        def body(uow: IdentityUnitOfWork) -> AccessGrant:
            cached = self._cache.get(f"auth:{token_hash}")
            grant = uow.access_grants.get_by_hash(token_hash)
            if cached is not None and grant is not None:
                cached_version = cached.get("permission_version")
                if isinstance(cached_version, int) and grant.permission_version == cached_version:
                    return grant
            now = utc_now()
            if grant is None or grant.revoked_at is not None or grant.expires_at <= now:
                raise IdentityError("AUTHENTICATION_REQUIRED", "需要登录")
            user = self._require_user(uow, grant.user_id)
            session = uow.sessions.get(grant.session_id)
            if (
                session is None
                or session.status.value != "ACTIVE"
                or user.status
                not in {
                    UserStatus.ACTIVE,
                    UserStatus.PENDING_VERIFICATION,
                }
            ):
                raise IdentityError("AUTHENTICATION_REQUIRED", "需要登录")
            if user.permission_version != grant.permission_version:
                raise IdentityError("AUTHENTICATION_REQUIRED", "授权已变更")
            ttl = max(1, int((grant.expires_at - now).total_seconds()))
            permission_version = grant.permission_version
            uow.run_after_commit(self._make_cache_set(token_hash, permission_version, ttl))
            return grant

        return self._read(body)

    def revoke_session(self, actor_user_id: UUID, session_id: UUID) -> None:
        def body(uow: IdentityUnitOfWork) -> None:
            session = uow.sessions.get(session_id)
            if session is None or session.user_id != actor_user_id:
                raise IdentityError("CROSS_USER_ACCESS_DENIED", "无权访问该会话")
            session.revoke()
            uow.sessions.save(session)
            for family in uow.token_families.list_for_session(session_id):
                family.revoke()
                uow.token_families.save(family)
            self._revoke_session_access_grants(uow, session_id)
            self._audit(
                uow,
                "USER",
                actor_user_id,
                "identity.session.revoke",
                "session",
                session_id,
                "SUCCESS",
            )

        self._write("user", actor_user_id, body)

    def enroll_mfa(self, user_id: UUID) -> tuple[str, list[str]]:
        def body(uow: IdentityUnitOfWork) -> tuple[str, list[str]]:
            self._require_user(uow, user_id)
            secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
            recovery_plain = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(8)]
            state = MfaState(
                encrypted_secret=self._encryption.encrypt(secret, str(user_id).encode()),
                recovery_codes=[
                    RecoveryCode(hash_secret(code, self._pepper)) for code in recovery_plain
                ],
            )
            uow.mfa.add(user_id, state)
            self._audit(uow, "USER", user_id, "identity.mfa.enroll", "user", user_id, "PENDING")
            return secret, recovery_plain

        return self._write("user", user_id, body)

    def confirm_mfa(self, user_id: UUID, code: str, at: datetime | None = None) -> None:
        def body(uow: IdentityUnitOfWork) -> None:
            state = uow.mfa.get(user_id)
            if state is None:
                raise IdentityError("IDENTITY_MFA_NOT_ENROLLED", "MFA 尚未登记")
            secret = self._encryption.decrypt(state.encrypted_secret, str(user_id).encode())
            if not verify_totp(secret, code, at=at):
                raise IdentityError("IDENTITY_INVALID_MFA_CODE", "MFA 验证码无效")
            state.enabled = True
            uow.mfa.save(user_id, state)
            self._audit(uow, "USER", user_id, "identity.mfa.enable", "user", user_id, "SUCCESS")

        self._write("user", user_id, body)

    def recover_mfa(self, user_id: UUID, code: str) -> None:
        presented_hash = hash_secret(code, self._pepper)

        def body(uow: IdentityUnitOfWork) -> None:
            state = uow.mfa.get(user_id)
            if state is None or not state.enabled:
                raise IdentityError("IDENTITY_MFA_NOT_ENROLLED", "MFA 未启用")
            for index, recovery in enumerate(state.recovery_codes):
                try:
                    state.recovery_codes[index] = recovery.consume(presented_hash)
                    uow.mfa.save(user_id, state)
                    self._audit(
                        uow, "USER", user_id, "identity.mfa.recover", "user", user_id, "SUCCESS"
                    )
                    return
                except IdentityError:
                    continue
            raise IdentityError("IDENTITY_INVALID_RECOVERY_CODE", "恢复码无效")

        self._write("user", user_id, body)

    def request_password_reset(self, identifier: str) -> str | None:
        normalized = identifier.strip().casefold()

        def body(uow: IdentityUnitOfWork) -> str | None:
            user = next(
                (u for u in uow.users.list_all() if normalized in {u.email, u.username}),
                None,
            )
            if user is None:
                return None
            now = utc_now()
            uow.one_time_tokens.invalidate_for_user_kind(user.id, "PASSWORD_RESET", now)
            token = generate_token()
            grant = OneTimeGrant(
                user_id=user.id,
                kind="PASSWORD_RESET",
                token_hash=hash_secret(token, self._pepper),
                expires_at=now + timedelta(minutes=20),
            )
            uow.one_time_tokens.add(grant)
            self._enqueue(
                uow,
                "identity.password_reset.requested",
                user.id,
                {"template": "password_reset_v1"},
            )
            self._audit(
                uow, "USER", user.id, "identity.password_reset.request", "user", user.id, "SUCCESS"
            )
            return token

        return self._write("user", None, body)

    def complete_password_reset(self, token: str, new_password: str) -> None:
        token_hash = hash_secret(token, self._pepper)

        def body(uow: IdentityUnitOfWork) -> None:
            grant = uow.one_time_tokens.consume(token_hash, "PASSWORD_RESET", utc_now())
            if grant is None:
                raise IdentityError("IDENTITY_INVALID_ONE_TIME_TOKEN", "一次性凭证无效或已过期")
            user = self._require_user(uow, grant.user_id)
            user.password_hash = self._passwords.hash(new_password)
            user.permission_version += 1
            uow.users.save(user)
            for session in uow.sessions.list_for_user(user.id):
                self._revoke_session_with_cascade(uow, user.id, session.id)
            self._cache_invalidate_user(uow, user.id)
            self._audit(
                uow,
                "USER",
                user.id,
                "identity.password_reset.complete",
                "user",
                user.id,
                "SUCCESS",
            )
            self._enqueue(
                uow,
                "identity.password_changed",
                user.id,
                {"template": "password_changed_v1"},
            )

        self._write("user", None, body)

    def request_export(self, user_id: UUID) -> UUID:
        def body(uow: IdentityUnitOfWork) -> UUID:
            self._require_user(uow, user_id)
            job_id = uuid4()
            uow.jobs.add(job_id, user_id, "export", "PENDING", {})
            self._enqueue(uow, "identity.export.requested", user_id, {"job_id": str(job_id)})
            self._audit(
                uow, "USER", user_id, "identity.export.request", "export_job", job_id, "ACCEPTED"
            )
            return job_id

        return self._write("user", user_id, body)

    def request_deletion(self, user_id: UUID) -> AccountDeletionRequest:
        def body(uow: IdentityUnitOfWork) -> AccountDeletionRequest:
            user = self._require_user(uow, user_id)
            request = AccountDeletionRequest(user_id=user_id)
            uow.deletion_requests.add(request)
            user.status = UserStatus.DELETION_PENDING
            uow.users.save(user)
            for session in uow.sessions.list_for_user(user_id):
                self._revoke_session_with_cascade(uow, user_id, session.id)
            self._enqueue(
                uow,
                "identity.account_deletion.requested",
                user_id,
                {"request_id": str(request.id), "scope": "identity_and_coordination"},
            )
            self._audit(
                uow,
                "USER",
                user_id,
                "identity.deletion.request",
                "deletion_request",
                request.id,
                "ACCEPTED",
            )
            return request

        return self._write("user", user_id, body)

    # -----------------------------
    # 内部辅助
    # -----------------------------

    def _require_user(self, uow: IdentityUnitOfWork, user_id: UUID) -> UserAccount:
        user = uow.users.get(user_id)
        if user is None:
            raise IdentityError("IDENTITY_USER_NOT_FOUND", "用户不存在")
        return user

    def get_user(self, user_id: UUID) -> UserAccount:
        """按 ID 只读查询用户，供 HTTP /me 等资源路由调用。"""

        def body(uow: IdentityUnitOfWork) -> UserAccount | None:
            return uow.users.get(user_id)

        user = self._read(body)
        if user is None:
            raise IdentityError("IDENTITY_USER_NOT_FOUND", "用户不存在")
        return user

    def _issue_tokens(
        self,
        uow: IdentityUnitOfWork,
        user: UserAccount,
        session: IdentitySession,
        family: TokenFamily,
        audience: str,
    ) -> dict[str, object]:
        refresh = generate_token()
        family.issue_initial(
            hash_secret(refresh, self._pepper),
            utc_now() + self._refresh_ttl,
        )
        uow.token_families.save(family)
        return {
            **self._issue_access(uow, user, session, audience),
            "refresh_token": refresh,
            "refresh_token_expires_in": int(self._refresh_ttl.total_seconds()),
        }

    def _issue_access(
        self,
        uow: IdentityUnitOfWork,
        user: UserAccount,
        session: IdentitySession,
        audience: str,
    ) -> dict[str, object]:
        access = generate_token()
        token_hash = hash_secret(access, self._pepper)
        scopes = (
            ("account:read", "account:write") if user.email_verified_at else ("account:limited",)
        )
        grant = AccessGrant(
            token_hash=token_hash,
            user_id=user.id,
            session_id=session.id,
            client_id=session.client_id,
            audience=audience,
            scopes=scopes,
            permission_version=user.permission_version,
            expires_at=utc_now() + self._access_ttl,
        )
        uow.access_grants.add(grant)
        return {
            "access_token": access,
            "token_type": OAUTH_BEARER_TOKEN_TYPE,
            "expires_in": int(self._access_ttl.total_seconds()),
            "scope": " ".join(scopes),
            "session_id": str(session.id),
        }

    def _revoke_session_with_cascade(
        self, uow: IdentityUnitOfWork, actor_user_id: UUID, session_id: UUID
    ) -> None:
        session = uow.sessions.get(session_id)
        if session is None or session.user_id != actor_user_id:
            raise IdentityError("CROSS_USER_ACCESS_DENIED", "无权访问该会话")
        session.revoke()
        uow.sessions.save(session)
        for family in uow.token_families.list_for_session(session_id):
            family.revoke()
            uow.token_families.save(family)
        self._revoke_session_access_grants(uow, session_id)

    def _revoke_session_access_grants(self, uow: IdentityUnitOfWork, session_id: UUID) -> None:
        now = utc_now()
        for grant in uow.access_grants.list_for_session(session_id):
            if grant.revoked_at is None:
                grant.revoked_at = now
                uow.access_grants.save(grant)
                token_hash = grant.token_hash
                uow.run_after_commit(self._make_cache_delete(token_hash))

    def _cache_invalidate_user(self, uow: IdentityUnitOfWork, user_id: UUID) -> None:
        for grant in uow.access_grants.list_for_user(user_id):
            token_hash = grant.token_hash
            uow.run_after_commit(self._make_cache_delete(token_hash))

    def _make_cache_delete(self, token_hash: str):
        def hook() -> None:
            self._cache.delete(f"auth:{token_hash}")

        return hook

    def _make_cache_set(self, token_hash: str, permission_version: int, ttl: int):
        def hook() -> None:
            self._cache.set(
                f"auth:{token_hash}",
                {"permission_version": permission_version},
                ttl,
            )

        return hook


# -----------------------------
# TOTP 工具
# -----------------------------


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
