"""FastAPI Composition Root。

所属层：Platform / Web。
职责：装配 Identity Service、JWT 密钥与 OAuth Client、创建 FastAPI 实例、
挂载 Identity Router、提供 Probe 与 lifespan。
边界：业务 DTO/路由/认证依赖由 `modules/identity/interfaces/http` 提供；
本模块不实现路由逻辑、不 commit、不读取 Secret 之外的业务状态。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from health_platform.modules.identity.application.in_memory_uow import InMemoryUnitOfWork
from health_platform.modules.identity.application.service import (
    IdentityService,
    OAuthClient,
)
from health_platform.modules.identity.domain.models import IdentityError
from health_platform.modules.identity.interfaces.http import (
    build_identity_router,
    identity_exception_adapter,
)
from health_platform.platform.background.worker import BackgroundWorker
from health_platform.platform.configuration.settings import Settings
from health_platform.platform.encryption.service import (
    AesGcmEncryptionService,
    StaticKeyManagementAdapter,
)
from health_platform.platform.security.oauth import JwtKeySet
from health_platform.platform.security.passwords import PasswordService


def _local_jwt_keys() -> JwtKeySet:
    """创建仅限 local/test 进程的临时签名密钥；生产必须使用挂载 Secret。"""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return JwtKeySet(pem, "local-ephemeral")


_DEFAULT_OAUTH_CLIENTS: tuple[OAuthClient, ...] = (
    OAuthClient(
        client_id="flutter-first-party",
        redirect_uris=("reboot-health://oauth/callback",),
        allowed_scopes=("openid", "profile", "account:read"),
        audience="health-platform-api",
    ),
)


def _register_default_oauth_clients(identity: IdentityService) -> None:
    """幂等注册第一方 OAuth Client；多 Pod 并发安全（UoW upsert）。"""
    identity.ensure_oauth_clients(list(_DEFAULT_OAUTH_CLIENTS))


def create_app(
    settings: Settings | None = None,
    identity: IdentityService | None = None,
    worker: BackgroundWorker | None = None,
    jwt_keys: JwtKeySet | None = None,
) -> FastAPI:
    """创建无导入副作用的 FastAPI 应用，允许测试注入全部基础设施。

    本轮 Slice 2 范围内 Composition Root 仍装配 InMemory UoW；生产 SQL
    Adapter、Engine、Settings 数据库强校验与 lifespan Alembic 升级属于
    下一轮切片。
    """
    cfg = settings or Settings()
    if identity is None:
        # 静态测试密钥只允许非生产；生产由 Composition Root 读取 Kubernetes Secret。
        if cfg.environment == "production":
            raise RuntimeError("production composition root requires mounted key adapters")
        encryption = AesGcmEncryptionService(
            StaticKeyManagementAdapter("local-v1", {"local-v1": b"0" * 32})
        )
        # 本轮 Slice 2 默认 Composition Root 装配共享 InMemory UoW；SQL Adapter
        # 与生产数据库属于下一轮切片。每次 create_app 调用一个独立 InMemory UoW
        # 单例，保证 HTTP 请求间状态一致。
        shared_uow = InMemoryUnitOfWork()

        def uow_factory():
            return shared_uow

        identity = IdentityService(
            PasswordService(),
            encryption,
            cfg.token_pepper.get_secret_value(),
            uow_factory=uow_factory,
            access_ttl=timedelta(seconds=cfg.access_token_ttl_seconds),
            refresh_ttl=timedelta(seconds=cfg.refresh_token_ttl_seconds),
        )
    background = worker or BackgroundWorker(lambda: False, cfg.outbox_poll_seconds)
    keys = jwt_keys or _local_jwt_keys()
    _register_default_oauth_clients(identity)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """统一启停后台线程；不使用裸 daemon 线程。"""
        background.start()
        app.state.startup_complete = True
        try:
            yield
        finally:
            background.stop(cfg.background_shutdown_timeout_seconds)

    app = FastAPI(
        title="reboot-health Health Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_exception_handler(IdentityError, identity_exception_adapter)
    app.state.identity = identity
    app.state.background = background
    app.state.settings = cfg

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
                status_code=503,
                content={"status": "not_ready", "reason": "background_worker"},
            )
        return JSONResponse(content={"status": "ready"})

    app.include_router(
        build_identity_router(settings=cfg, identity=identity, jwt_keys=keys),
        prefix="/api/v1",
    )
    return app


app = create_app()
