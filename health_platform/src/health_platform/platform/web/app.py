"""FastAPI Composition Root 与 Identity HTTP 接口。

所属层：Platform / Web 与 Identity / Interfaces。
职责：DTO、Header、错误、认证依赖、OpenAPI、Probe 和 lifespan。
边界：Router 不 commit、不散落角色判断、不返回内部异常或 Secret。
"""

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from health_platform.modules.identity.application.service import IdentityService, OAuthClient
from health_platform.modules.identity.domain.models import IdentityError
from health_platform.platform.background.worker import BackgroundWorker
from health_platform.platform.configuration.settings import Settings
from health_platform.platform.encryption.service import (
    AesGcmEncryptionService,
    StaticKeyManagementAdapter,
)
from health_platform.platform.security.oauth import JwtKeySet
from health_platform.platform.security.passwords import PasswordService


class RegisterRequest(BaseModel):
    """注册请求 DTO。"""

    email: str
    username: str
    display_name: str
    password: str = Field(min_length=12, max_length=1024)


class LoginRequest(BaseModel):
    """统一邮箱/用户名登录 DTO。"""

    identifier: str
    password: str
    client_id: str
    device_name: str
    client_type: str


class TokenRequest(BaseModel):
    """Refresh Token Grant DTO。"""

    grant_type: str
    refresh_token: str | None = None
    code: str | None = None
    client_id: str | None = None
    redirect_uri: str | None = None
    code_verifier: str | None = None


class AuthorizeRequest(BaseModel):
    """第一方 Authorization Code + PKCE 请求 DTO。"""

    client_id: str
    redirect_uri: str
    scope: str
    state: str
    nonce: str
    code_challenge: str
    code_challenge_method: str


class TokenValueRequest(BaseModel):
    """一次性 Token DTO。"""

    token: str


class MfaCodeRequest(BaseModel):
    """MFA 验证/恢复 DTO。"""

    code: str


class PasswordResetRequest(BaseModel):
    """密码恢复申请 DTO。"""

    identifier: str


class PasswordResetCompleteRequest(BaseModel):
    """密码恢复完成 DTO。"""

    token: str
    new_password: str = Field(min_length=12, max_length=1024)


def _local_jwt_keys() -> JwtKeySet:
    """创建仅限 local/test 进程的临时签名密钥；生产必须使用挂载 Secret。"""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return JwtKeySet(pem, "local-ephemeral")


def create_app(
    settings: Settings | None = None,
    identity: IdentityService | None = None,
    worker: BackgroundWorker | None = None,
    jwt_keys: JwtKeySet | None = None,
) -> FastAPI:
    """创建无导入副作用的 FastAPI 应用，允许测试注入全部基础设施。"""
    cfg = settings or Settings()
    if identity is None:
        # 静态测试密钥只允许非生产；生产由 Composition Root 读取 Kubernetes Secret。
        if cfg.environment == "production":
            raise RuntimeError("production composition root requires mounted key adapters")
        encryption = AesGcmEncryptionService(
            StaticKeyManagementAdapter("local-v1", {"local-v1": b"0" * 32})
        )
        identity = IdentityService(
            PasswordService(),
            encryption,
            cfg.token_pepper.get_secret_value(),
            access_ttl=timedelta(seconds=cfg.access_token_ttl_seconds),
            refresh_ttl=timedelta(seconds=cfg.refresh_token_ttl_seconds),
        )
    background = worker or BackgroundWorker(lambda: False, cfg.outbox_poll_seconds)
    keys = jwt_keys or _local_jwt_keys()
    if "flutter-first-party" not in identity.state.oauth_clients:
        identity.register_oauth_client(
            OAuthClient(
                client_id="flutter-first-party",
                redirect_uris=("reboot-health://oauth/callback",),
                allowed_scopes=("openid", "profile", "account:read"),
                audience="health-platform-api",
            )
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """统一启停后台线程；不使用裸 daemon 线程。"""
        background.start()
        app.state.startup_complete = True
        try:
            yield
        finally:
            background.stop(cfg.background_shutdown_timeout_seconds)

    app = FastAPI(title="reboot-health Health Platform", version="0.1.0", lifespan=lifespan)
    app.state.identity = identity
    app.state.background = background
    app.state.settings = cfg

    @app.exception_handler(IdentityError)
    async def identity_error_handler(request: Request, exc: IdentityError) -> JSONResponse:
        """将领域错误转换为稳定模型，不返回 traceback、SQL 或内部地址。"""
        status = (
            401 if exc.code in {"AUTHENTICATION_REQUIRED", "IDENTITY_INVALID_CREDENTIALS"} else 400
        )
        return JSONResponse(
            status_code=status,
            content={
                "error_code": exc.code,
                "message": str(exc),
                "trace_id": request.headers.get("x-trace-id", "unavailable"),
                "details": {},
            },
        )

    def principal(authorization: Annotated[str | None, Header()] = None) -> tuple[UUID, str]:
        """解析 Bearer Token 并返回最小 UserPrincipal；Token 不写日志。"""
        if not authorization or not authorization.startswith("Bearer "):
            raise IdentityError("AUTHENTICATION_REQUIRED", "需要登录")
        token = authorization.removeprefix("Bearer ").strip()
        grant = identity.authenticate(token)
        return grant.user_id, token

    @app.get("/health/live")
    def live() -> dict[str, str]:
        """只证明进程与事件循环可响应，不因外部依赖抖动触发重启。"""
        return {"status": "live"}

    @app.get("/health/startup")
    def startup() -> dict[str, str]:
        """报告配置和 Composition Root 已完成。"""
        return {"status": "started"}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        """检查后台线程 heartbeat；数据库/Alembic checker 由生产 Composition Root 扩展。"""
        if not background.is_alive:
            return JSONResponse(
                status_code=503, content={"status": "not_ready", "reason": "background_worker"}
            )
        return JSONResponse(content={"status": "ready"})

    @app.post("/api/v1/identity/register", status_code=201)
    def register(body: RegisterRequest) -> dict[str, Any]:
        """注册并返回账号资源；验证 Token 仅由邮件 Outbox 发送，不在响应中泄露。"""
        user, _ = identity.register(body.email, body.username, body.display_name, body.password)
        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "status": user.status.value,
            "email_verified": False,
        }

    @app.post("/api/v1/identity/login")
    def login(body: LoginRequest) -> dict[str, Any]:
        """登录并签发设备独立不透明 Token。"""
        return identity.login(
            body.identifier, body.password, body.client_id, body.device_name, body.client_type
        )

    @app.post("/api/v1/identity/email-verifications/confirm")
    def verify_email(body: TokenValueRequest) -> dict[str, Any]:
        """一次性确认邮箱。"""
        user = identity.verify_email(body.token)
        return {"id": str(user.id), "email_verified": True, "status": user.status.value}

    @app.post("/api/v1/oauth/token")
    def token(body: TokenRequest) -> dict[str, Any]:
        """处理 Authorization Code/PKCE 与 Refresh Token Grant。"""
        if body.grant_type == "refresh_token" and body.refresh_token:
            return identity.refresh(body.refresh_token)
        if body.grant_type == "authorization_code" and all(
            (body.code, body.client_id, body.redirect_uri, body.code_verifier)
        ):
            result, user, nonce = identity.exchange_authorization_code(
                body.code or "",
                body.client_id or "",
                body.redirect_uri or "",
                body.code_verifier or "",
            )
            result["id_token"] = keys.sign(
                str(user.id),
                body.client_id or "",
                cfg.issuer,
                timedelta(minutes=5),
                {"nonce": nonce},
            )
            return result
        raise IdentityError("IDENTITY_UNSUPPORTED_GRANT", "不支持的 grant_type")

    @app.post("/api/v1/oauth/authorize")
    def authorize(
        body: AuthorizeRequest,
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> dict[str, str]:
        """验证 S256、state、nonce 后返回一次性短期授权码。"""
        if body.code_challenge_method != "S256" or not body.state or not body.nonce:
            raise IdentityError("IDENTITY_INVALID_AUTHORIZATION_REQUEST", "授权请求无效")
        code = identity.authorize(
            principal_value[0],
            body.client_id,
            body.redirect_uri,
            tuple(body.scope.split()),
            body.nonce,
            body.code_challenge,
        )
        return {"code": code, "state": body.state, "redirect_uri": body.redirect_uri}

    @app.post("/api/v1/oauth/revoke", status_code=204)
    def revoke(principal_value: Annotated[tuple[UUID, str], Depends(principal)]) -> None:
        """撤销当前 Session；响应不暴露 Token 状态。"""
        user_id, token_value = principal_value
        grant = identity.authenticate(token_value)
        identity.revoke_session(user_id, grant.session_id)

    @app.get("/api/v1/identity/me")
    def me(principal_value: Annotated[tuple[UUID, str], Depends(principal)]) -> dict[str, Any]:
        """返回当前账号最小资料，不包含权限内部结构或健康数据。"""
        user_id, _ = principal_value
        user = identity.state.users[user_id]
        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "status": user.status.value,
            "email_verified": user.email_verified_at is not None,
        }

    @app.post("/api/v1/identity/mfa/totp/enroll")
    def mfa_enroll(
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> dict[str, Any]:
        """返回仅展示一次的 TOTP Secret 与恢复码。"""
        secret, recovery_codes = identity.enroll_mfa(principal_value[0])
        return {"totp_secret": secret, "recovery_codes": recovery_codes}

    @app.post("/api/v1/identity/mfa/totp/confirm", status_code=204)
    def mfa_confirm(
        body: MfaCodeRequest, principal_value: Annotated[tuple[UUID, str], Depends(principal)]
    ) -> None:
        """确认 TOTP enrollment。"""
        identity.confirm_mfa(principal_value[0], body.code)

    @app.post("/api/v1/identity/mfa/recover", status_code=204)
    def mfa_recover(
        body: MfaCodeRequest, principal_value: Annotated[tuple[UUID, str], Depends(principal)]
    ) -> None:
        """消费一次性恢复码。"""
        identity.recover_mfa(principal_value[0], body.code)

    @app.post("/api/v1/identity/password-recovery", status_code=202)
    def password_recovery(body: PasswordResetRequest) -> dict[str, str]:
        """始终返回模糊成功，防止账号枚举。"""
        identity.request_password_reset(body.identifier)
        return {"status": "accepted"}

    @app.post("/api/v1/identity/password-recovery/complete", status_code=204)
    def password_recovery_complete(body: PasswordResetCompleteRequest) -> None:
        """完成重置并撤销全部会话。"""
        identity.complete_password_reset(body.token, body.new_password)

    @app.post("/api/v1/identity/exports", status_code=202)
    def export(principal_value: Annotated[tuple[UUID, str], Depends(principal)]) -> dict[str, str]:
        """创建 Identity 导出任务框架。"""
        return {"job_id": str(identity.request_export(principal_value[0])), "status": "PENDING"}

    @app.post("/api/v1/identity/deletion-requests", status_code=202)
    def deletion(
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> dict[str, str]:
        """创建七天冷静期删除请求并撤销全部会话。"""
        request = identity.request_deletion(principal_value[0])
        return {
            "request_id": str(request.id),
            "status": "COOLING_OFF",
            "ready_at": request.ready_at.isoformat(),
        }

    @app.get("/api/v1/.well-known/openid-configuration")
    def discovery() -> dict[str, Any]:
        """发布第一方 OIDC Discovery。"""
        return {
            "issuer": cfg.issuer,
            "authorization_endpoint": f"{cfg.issuer}/oauth/authorize",
            "token_endpoint": f"{cfg.issuer}/oauth/token",
            "revocation_endpoint": f"{cfg.issuer}/oauth/revoke",
            "jwks_uri": f"{cfg.issuer}/.well-known/jwks.json",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
            "code_challenge_methods_supported": ["S256"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }

    @app.get("/api/v1/.well-known/jwks.json")
    def jwks() -> dict[str, Any]:
        """仅发布 current/previous 公钥。"""
        return keys.jwks()

    return app


app = create_app()
