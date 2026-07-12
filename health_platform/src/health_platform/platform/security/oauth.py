"""OAuth/OIDC 确定性安全原语。

所属层：Platform / Security。
职责：S256 PKCE、Redirect URI 精确匹配、JWT 固定算法签发与 JWKS。
边界：OAuthLib/FastAPI 适配器负责编排；本模块不访问数据库或接受客户端算法。
"""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from joserfc import jwt
from joserfc.jwk import RSAKey

from health_platform.modules.identity.domain.models import IdentityError, generate_token


def pkce_challenge(verifier: str) -> str:
    """计算 RFC 7636 S256 challenge；禁止 plain 模式降低授权码安全性。"""
    if not 43 <= len(verifier) <= 128:
        raise IdentityError("IDENTITY_INVALID_PKCE", "PKCE verifier 无效")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_pkce(verifier: str, expected_challenge: str) -> bool:
    """恒定时间验证 S256 PKCE，避免 verifier 比较泄露。"""
    try:
        actual = pkce_challenge(verifier)
    except (IdentityError, UnicodeEncodeError):
        return False
    return (
        hashlib.sha256(actual.encode()).digest()
        == hashlib.sha256(expected_challenge.encode()).digest()
    )


def validate_redirect_uri(uri: str, allowed: tuple[str, ...]) -> None:
    """精确匹配预注册 Redirect URI，不允许前缀、通配符或重定向扩权。"""
    if uri not in allowed:
        raise IdentityError("IDENTITY_REDIRECT_URI_MISMATCH", "redirect_uri 不匹配")


class JwtKeySet:
    """固定 RS256 的 current/previous 密钥集；私钥只从挂载文件加载。"""

    def __init__(
        self,
        current_private_pem: str,
        current_kid: str,
        previous_public_pem: str | None = None,
        previous_kid: str | None = None,
    ) -> None:
        self._current = RSAKey.import_key(current_private_pem)
        self._current_kid = current_kid
        self._previous = RSAKey.import_key(previous_public_pem) if previous_public_pem else None
        self._previous_kid = previous_kid

    def sign(
        self,
        subject: str,
        audience: str,
        issuer: str,
        ttl: timedelta,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """固定 RS256 签发短期 JWT；调用方不能指定算法或密钥。"""
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "iss": issuer,
            "sub": subject,
            "aud": audience,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + ttl).timestamp()),
            "jti": generate_token(),
        }
        claims.update(extra_claims or {})
        return jwt.encode({"alg": "RS256", "kid": self._current_kid}, claims, self._current)

    def jwks(self) -> dict[str, list[dict[str, Any]]]:
        """仅发布公钥，保留 previous key 完成无中断轮换窗口。"""
        keys: list[dict[str, Any]] = []
        for key, kid in (
            (self._current, self._current_kid),
            (self._previous, self._previous_kid),
        ):
            if key is None or kid is None:
                continue
            public = dict(key.as_dict(private=False))
            public.update({"kid": kid, "use": "sig", "alg": "RS256"})
            keys.append(public)
        return {"keys": keys}
