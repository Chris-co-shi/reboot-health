"""FastAPI Composition Root。

所属层：Platform / Web。
职责：装配 Identity Service、JWT 密钥与 OAuth Client、创建 FastAPI 实例、
挂载 Identity Router、提供 Probe 与 lifespan。
边界：业务 DTO/路由/认证依赖由 `modules/identity/interfaces/http` 提供；
本模块不实现路由逻辑、不 commit、不读取 Secret 之外的业务状态。
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis import Redis

from health_platform.modules.identity.adapters.email import (
    DevelopmentCaptureEmailAdapter,
    SmtpEmailAdapter,
)
from health_platform.modules.identity.application.in_memory_uow import InMemoryUnitOfWork
from health_platform.modules.identity.application.ports import IdentityUnitOfWork, UoWFactory
from health_platform.modules.identity.application.service import IdentityService, OAuthClient
from health_platform.modules.identity.domain.models import IdentityError
from health_platform.modules.identity.interfaces.http import (
    build_identity_router,
    identity_exception_adapter,
)
from health_platform.modules.identity.ports.email import EmailPort
from health_platform.platform.background.worker import BackgroundWorker
from health_platform.platform.configuration.settings import Settings
from health_platform.platform.database.core import (
    create_database_engine,
    create_session_factory,
)
from health_platform.platform.database.readiness import (
    ReadinessResult,
    check_database_readiness,
)
from health_platform.platform.database.sqlalchemy_uow import SqlAlchemyIdentityUnitOfWork
from health_platform.platform.encryption.service import (
    AesGcmEncryptionService,
    FileKeyManagementAdapter,
    StaticKeyManagementAdapter,
)
from health_platform.platform.security.cache import RedisAuthCache
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


def _oauth_client(settings: Settings) -> OAuthClient:
    """生产读取显式配置；local/test 使用稳定第一方测试配置。"""
    return OAuthClient(
        client_id=settings.oauth_first_party_client_id or "flutter-first-party",
        redirect_uris=settings.oauth_first_party_redirect_uris
        or ("reboot-health://oauth/callback",),
        allowed_scopes=settings.oauth_first_party_scopes,
        audience=settings.oauth_first_party_audience,
    )


def _register_default_oauth_clients(identity: IdentityService, settings: Settings) -> None:
    """幂等注册第一方 OAuth Client；多 Pod 并发安全（UoW upsert）。"""
    identity.ensure_oauth_clients([_oauth_client(settings)])


def create_app(
    settings: Settings | None = None,
    identity: IdentityService | None = None,
    worker: BackgroundWorker | None = None,
    jwt_keys: JwtKeySet | None = None,
    readiness_check: Callable[[], ReadinessResult] | None = None,
) -> FastAPI:
    """创建无导入副作用的 FastAPI 应用，允许测试注入全部基础设施。

    local/test 默认使用 InMemory；production 在未注入测试依赖时只装配 PostgreSQL。
    """
    cfg = settings or Settings()
    engine = None
    email: EmailPort = DevelopmentCaptureEmailAdapter()
    uow_factory: UoWFactory
    if identity is None:
        if cfg.environment == "production":
            if cfg.database_url is None or cfg.encryption_key_file is None:
                raise RuntimeError("production persistence configuration is incomplete")
            engine = create_database_engine(cfg.database_url)
            session_factory = create_session_factory(engine)

            def sql_uow_factory() -> IdentityUnitOfWork:
                return SqlAlchemyIdentityUnitOfWork(session_factory)

            uow_factory = sql_uow_factory
            key_adapter = FileKeyManagementAdapter(cfg.encryption_key_file)
            configured_version = cfg.encryption_current_key_version
            if configured_version is None or key_adapter.current()[0] != configured_version:
                raise RuntimeError("production encryption key version mismatch")
            encryption = AesGcmEncryptionService(key_adapter)
            cache = (
                RedisAuthCache(Redis.from_url(cfg.redis_url))
                if cfg.redis_enabled and cfg.redis_url
                else None
            )
            if cfg.smtp_host:
                email = SmtpEmailAdapter(
                    cfg.smtp_host,
                    cfg.smtp_port,
                    cfg.smtp_from,
                    cfg.smtp_username,
                    cfg.smtp_password.get_secret_value() if cfg.smtp_password else None,
                )
            if jwt_keys is None:
                if cfg.oidc_private_key_file is None:
                    raise RuntimeError("production signing key is missing")
                jwt_keys = JwtKeySet(
                    Path(cfg.oidc_private_key_file).read_text(encoding="utf-8"),
                    cfg.oidc_current_kid,
                    Path(cfg.oidc_previous_public_key_file).read_text(encoding="utf-8")
                    if cfg.oidc_previous_public_key_file
                    else None,
                    cfg.oidc_previous_kid,
                )
            if readiness_check is None:
                alembic_ini = Path(__file__).parents[4] / "alembic.ini"

                def production_readiness() -> ReadinessResult:
                    if engine is None:
                        return ReadinessResult(False, "database_unavailable")
                    return check_database_readiness(engine, alembic_ini)

                readiness_check = production_readiness
        else:
            encryption = AesGcmEncryptionService(
                StaticKeyManagementAdapter("local-v1", {"local-v1": b"0" * 32})
            )
            shared_uow = InMemoryUnitOfWork()

            def memory_uow_factory() -> InMemoryUnitOfWork:
                return shared_uow

            uow_factory = memory_uow_factory
            cache = None

        identity = IdentityService(
            PasswordService(),
            encryption,
            cfg.token_pepper.get_secret_value(),
            uow_factory=uow_factory,
            cache=cache,
            access_ttl=timedelta(seconds=cfg.access_token_ttl_seconds),
            refresh_ttl=timedelta(seconds=cfg.refresh_token_ttl_seconds),
        )
    background = worker or BackgroundWorker(lambda: False, cfg.outbox_poll_seconds)
    keys = jwt_keys or _local_jwt_keys()
    _register_default_oauth_clients(identity, cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """统一启停后台线程；不使用裸 daemon 线程。"""
        background.start()
        app.state.startup_complete = True
        try:
            yield
        finally:
            background.stop(cfg.background_shutdown_timeout_seconds)
            if engine is not None:
                engine.dispose()

    app = FastAPI(
        title="reboot-health Health Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_exception_handler(IdentityError, identity_exception_adapter)
    app.state.identity = identity
    app.state.background = background
    app.state.settings = cfg
    app.state.engine = engine
    app.state.email = email

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
        """检查后台线程、PostgreSQL 与 Alembic revision，不修改数据库。"""
        if not background.is_alive:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "background_worker"},
            )
        if readiness_check is not None:
            result = readiness_check()
            if not result.ready:
                return JSONResponse(
                    status_code=503,
                    content={"status": "not_ready", "reason": result.reason},
                )
        return JSONResponse(content={"status": "ready"})

    app.include_router(
        build_identity_router(settings=cfg, identity=identity, jwt_keys=keys),
        prefix="/api/v1",
    )
    return app


app = create_app()
