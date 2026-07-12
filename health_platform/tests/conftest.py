"""测试公共 fixture：IdentityService 装配 InMemoryUnitOfWork。

本轮 Slice 2 仅引入 Port 抽象与 InMemory UoW；SqlAlchemy 实现与生产
Composition Root 属于下一轮切片。
"""

from __future__ import annotations

import pytest

from health_platform.modules.identity.application.in_memory_uow import InMemoryUnitOfWork
from health_platform.modules.identity.application.service import IdentityService
from health_platform.platform.encryption.service import (
    AesGcmEncryptionService,
    StaticKeyManagementAdapter,
)
from health_platform.platform.security.passwords import PasswordService


@pytest.fixture
def in_memory_uow() -> InMemoryUnitOfWork:
    """提供共享 InMemory UoW；测试代码可通过 fixture 读取审计/Outbox 条目。"""
    return InMemoryUnitOfWork()


@pytest.fixture
def uow_factory(in_memory_uow: InMemoryUnitOfWork):
    """返回创建新 InMemory UoW 的工厂；每个用例都获得独立事务边界。

    通过闭包捕获 in_memory_uow 实例但每次返回新对象，使 Service 在 _write
    中通过 `with self._uow_factory() as uow` 进入独立事务；测试断言通过
    in_memory_uow fixture 读取最后状态。
    """
    return lambda: InMemoryUnitOfWork()


@pytest.fixture
def service(uow_factory) -> IdentityService:
    encryption = AesGcmEncryptionService(StaticKeyManagementAdapter("v1", {"v1": b"x" * 32}))
    return IdentityService(PasswordService(), encryption, "pepper", uow_factory=uow_factory)
