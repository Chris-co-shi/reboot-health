"""密码安全实现。

所属层：Platform / Security。
职责：密码策略、Argon2id 哈希与验证。
边界：不记录、持久化或返回密码，不执行账号枚举判断。
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from health_platform.modules.identity.domain.models import IdentityError

_COMMON_PASSWORDS = frozenset(
    {
        "passwordpassword",
        "123456789012",
        "qwertyuiop12",
        "letmeinletmein",
        "adminadminadmin",
    }
)


class PasswordService:
    """使用 Argon2id 的密码服务；参数由库的安全默认值统一管理。"""

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher()

    def validate_policy(self, password: str, breached: bool = False) -> None:
        """拒绝短、常见或已泄露密码，但不强制脆弱的字符组合规则。"""
        if len(password) < 12:
            raise IdentityError("IDENTITY_WEAK_PASSWORD", "密码至少需要 12 位")
        if len(password) > 1024:
            raise IdentityError("IDENTITY_WEAK_PASSWORD", "密码长度超过安全处理上限")
        if password.casefold() in _COMMON_PASSWORDS or breached:
            raise IdentityError("IDENTITY_COMPROMISED_PASSWORD", "该密码不可使用")

    def hash(self, password: str, breached: bool = False) -> str:
        """校验策略并生成 Argon2id 哈希。"""
        self.validate_policy(password, breached=breached)
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """安全验证密码；格式错误与不匹配均返回相同结果以避免信息泄露。"""
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
