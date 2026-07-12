"""Identity HTTP 接口。

所属层：Identity / Interfaces。
职责：DTO、Header、错误、认证依赖、OpenAPI、Identity/OAuth/OIDC 路由。
边界：Router 不 commit、不散落角色判断、不返回内部异常或 Secret。
路径与响应与原 `platform/web/app.py` 保持一致；Composition Root 负责把
生成的 router 挂到 `/api/v1` 前缀下。
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from health_platform.modules.identity.application.service import IdentityService
from health_platform.modules.identity.domain.models import IdentityError
from health_platform.platform.configuration.settings import Settings
from health_platform.platform.security.oauth import JwtKeySet


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


def identity_error_handler(request: Request, exc: IdentityError) -> JSONResponse:
    """将领域错误转换为稳定模型，不返回 traceback、SQL 或内部地址。

    本函数以 `IdentityError` 精确签名为业务内部入口；FastAPI 的
    `Exception` 处理器不协变，需要由 `identity_exception_adapter` 以
    `(Request, Exception) -> JSONResponse` 签名适配后注册到 app 上，
    以满足 Starlette `add_exception_handler` 的类型约束。
    """
    status = 401 if exc.code in {"AUTHENTICATION_REQUIRED", "IDENTITY_INVALID_CREDENTIALS"} else 400
    return JSONResponse(
        status_code=status,
        content={
            "error_code": exc.code,
            "message": str(exc),
            "trace_id": request.headers.get("x-trace-id", "unavailable"),
            "details": {},
        },
    )


def identity_exception_adapter(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI/Starlette 要求的 `(Request, Exception)` 签名适配器。

    Composition Root 在 app 上注册此适配器；内部用 `isinstance` 收窄为
    `IdentityError` 后调用 `identity_error_handler`，不引入 `type: ignore`，
    也不依赖 `APIRouter.add_exception_handler`（未确认支持）。
    """
    if isinstance(exc, IdentityError):
        return identity_error_handler(request, exc)
    # 非 `IdentityError` 不会路由到此处理器；为防御性回退返回通用 500。
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "IDENTITY_INTERNAL_ERROR",
            "message": "内部错误",
            "trace_id": request.headers.get("x-trace-id", "unavailable"),
            "details": {},
        },
    )


def build_identity_router(
    settings: Settings,
    identity: IdentityService,
    jwt_keys: JwtKeySet,
) -> APIRouter:
    """构造只暴露 Identity/OAuth/OIDC 路由的 APIRouter。

    所有路由以 `/api/v1` 为根，由 Composition Root 负责挂载。
    `IdentityError` 处理由 Composition Root 在 FastAPI app 上显式注册。
    """
    router = APIRouter()

    def principal(
        authorization: Annotated[str | None, Header()] = None,
    ) -> tuple[UUID, str]:
        """解析 Bearer Token 并返回最小 UserPrincipal；Token 不写日志。"""
        if not authorization or not authorization.startswith("Bearer "):
            raise IdentityError("AUTHENTICATION_REQUIRED", "需要登录")
        token = authorization.removeprefix("Bearer ").strip()
        grant = identity.authenticate(token)
        return grant.user_id, token

    @router.post("/identity/register", status_code=201)
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

    @router.post("/identity/login")
    def login(body: LoginRequest) -> dict[str, Any]:
        """登录并签发设备独立不透明 Token。"""
        return identity.login(
            body.identifier,
            body.password,
            body.client_id,
            body.device_name,
            body.client_type,
        )

    @router.post("/identity/email-verifications/confirm")
    def verify_email(body: TokenValueRequest) -> dict[str, Any]:
        """一次性确认邮箱。"""
        user = identity.verify_email(body.token)
        return {"id": str(user.id), "email_verified": True, "status": user.status.value}

    @router.post("/oauth/token")
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
            result["id_token"] = jwt_keys.sign(
                str(user.id),
                body.client_id or "",
                settings.issuer,
                timedelta(minutes=5),
                {"nonce": nonce},
            )
            return result
        raise IdentityError("IDENTITY_UNSUPPORTED_GRANT", "不支持的 grant_type")

    @router.post("/oauth/authorize")
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

    @router.post("/oauth/revoke", status_code=204)
    def revoke(
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> None:
        """撤销当前 Session；响应不暴露 Token 状态。"""
        user_id, token_value = principal_value
        grant = identity.authenticate(token_value)
        identity.revoke_session(user_id, grant.session_id)

    @router.get("/identity/me")
    def me(
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> dict[str, Any]:
        """返回当前账号最小资料，不包含权限内部结构或健康数据。"""
        user_id, _ = principal_value
        user = identity.get_user(user_id)
        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "status": user.status.value,
            "email_verified": user.email_verified_at is not None,
        }

    @router.post("/identity/mfa/totp/enroll")
    def mfa_enroll(
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> dict[str, Any]:
        """返回仅展示一次的 TOTP Secret 与恢复码。"""
        secret, recovery_codes = identity.enroll_mfa(principal_value[0])
        return {"totp_secret": secret, "recovery_codes": recovery_codes}

    @router.post("/identity/mfa/totp/confirm", status_code=204)
    def mfa_confirm(
        body: MfaCodeRequest,
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> None:
        """确认 TOTP enrollment。"""
        identity.confirm_mfa(principal_value[0], body.code)

    @router.post("/identity/mfa/recover", status_code=204)
    def mfa_recover(
        body: MfaCodeRequest,
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> None:
        """消费一次性恢复码。"""
        identity.recover_mfa(principal_value[0], body.code)

    @router.post("/identity/password-recovery", status_code=202)
    def password_recovery(body: PasswordResetRequest) -> dict[str, str]:
        """始终返回模糊成功，防止账号枚举。"""
        identity.request_password_reset(body.identifier)
        return {"status": "accepted"}

    @router.post("/identity/password-recovery/complete", status_code=204)
    def password_recovery_complete(body: PasswordResetCompleteRequest) -> None:
        """完成重置并撤销全部会话。"""
        identity.complete_password_reset(body.token, body.new_password)

    @router.post("/identity/exports", status_code=202)
    def export(
        principal_value: Annotated[tuple[UUID, str], Depends(principal)],
    ) -> dict[str, str]:
        """创建 Identity 导出任务框架。"""
        return {
            "job_id": str(identity.request_export(principal_value[0])),
            "status": "PENDING",
        }

    @router.post("/identity/deletion-requests", status_code=202)
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

    @router.get("/.well-known/openid-configuration")
    def discovery() -> dict[str, Any]:
        """发布第一方 OIDC Discovery。"""
        return {
            "issuer": settings.issuer,
            "authorization_endpoint": f"{settings.issuer}/oauth/authorize",
            "token_endpoint": f"{settings.issuer}/oauth/token",
            "revocation_endpoint": f"{settings.issuer}/oauth/revoke",
            "jwks_uri": f"{settings.issuer}/.well-known/jwks.json",
            "response_types_supported": ["code"],
            "grant_types_supported": [
                "authorization_code",
                "refresh_token",
                "client_credentials",
            ],
            "code_challenge_methods_supported": ["S256"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }

    @router.get("/.well-known/jwks.json")
    def jwks() -> dict[str, Any]:
        """仅发布 current/previous 公钥。"""
        return jwt_keys.jwks()

    return router


# `principal` 工厂签名供 Composition Root 与测试复用；保留为模块级 callable 以便
# 类型检查与未来扩展（如自定义 Cache/MFA 校验）能在不破坏路径的情况下替换。
PrincipalFactory = Callable[[], Callable[..., tuple[UUID, str]]]
