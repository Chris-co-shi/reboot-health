"""应用配置模型。

所属层：Platform / Configuration。
职责：集中校验环境、数据库、Redis、OAuth、加密和后台线程配置。
边界：不创建基础设施客户端，不输出 Secret，不提供生产默认密钥。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Health Platform 启动配置；生产关键 Secret 缺失时拒绝启动。"""

    model_config = SettingsConfigDict(env_prefix="HEALTH_PLATFORM_", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    service_name: str = "health-platform"
    database_url: str | None = None
    redis_url: str | None = None
    redis_enabled: bool = False
    token_pepper: SecretStr = Field(default=SecretStr("local-test-token-pepper"))
    encryption_key_file: str | None = None
    encryption_current_key_version: str | None = None
    oidc_private_key_file: str | None = None
    oidc_previous_public_key_file: str | None = None
    oidc_current_kid: str = "local-current"
    oidc_previous_kid: str | None = None
    issuer: str = "http://localhost:8000/api/v1"
    oauth_first_party_client_id: str | None = None
    oauth_first_party_redirect_uris: tuple[str, ...] = ()
    oauth_first_party_scopes: tuple[str, ...] = ("openid", "profile", "account:read")
    oauth_first_party_audience: str = "health-platform-api"
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_seconds: int = Field(default=2_592_000, ge=3600)
    verification_token_ttl_seconds: int = Field(default=1800, ge=300, le=86_400)
    authorization_code_ttl_seconds: int = Field(default=300, ge=60, le=600)
    outbox_poll_seconds: float = Field(default=1.0, gt=0, le=60)
    outbox_lock_seconds: int = Field(default=30, ge=5, le=600)
    background_heartbeat_timeout_seconds: int = Field(default=30, ge=5, le=600)
    background_shutdown_timeout_seconds: int = Field(default=15, ge=1, le=120)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "no-reply@example.invalid"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """保证生产环境不会误用仅为本地测试准备的默认 Secret。"""
        if self.environment == "production":
            if not self.database_url or not self.database_url.startswith(
                ("postgresql+psycopg://", "postgresql://")
            ):
                raise ValueError("production requires an explicit PostgreSQL database URL")
            if self.token_pepper.get_secret_value() == "local-test-token-pepper":
                raise ValueError("production requires an explicit token pepper")
            if (
                not self.encryption_key_file
                or not self.encryption_current_key_version
                or not self.oidc_private_key_file
            ):
                raise ValueError("production requires mounted encryption and signing keys")
            if not self.oauth_first_party_client_id or not self.oauth_first_party_redirect_uris:
                raise ValueError("production requires first-party OAuth client configuration")
        return self

    def safe_summary(self) -> dict[str, object]:
        """返回可记录的非敏感配置摘要，避免 Secret 被 repr 或日志泄露。"""
        return {
            "environment": self.environment,
            "service_name": self.service_name,
            "redis_enabled": self.redis_enabled,
            "issuer": self.issuer,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """为 Composition Root 提供进程级不可变配置快照。"""
    return Settings()
