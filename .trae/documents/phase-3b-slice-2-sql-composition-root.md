# Phase 3B Slice 2 — 生产 SQL Composition Root 规划（修订版）

## Summary

把 Identity 路径从内存 `IdentityState` 切到 PostgreSQL + SQLAlchemy UoW；FastAPI 默认生产路径不再读写内存状态；Audit/Outbox 与业务数据同事务提交；Repository / Router 不 commit；事务内禁止 Redis / SMTP / HTTP 等远程 I/O。Production 配置缺数据库或密钥即启动失败。补充 5 项真实 PostgreSQL 集成测试覆盖重启保留、事务回滚、审计原子性、Refresh 并发轮换、Redis 故障回退。Slice 2 与 Phase 3B 保持 `IN_PROGRESS`。

`IdentityService` 不再保留 `self.state` 与 SQL 双分支；应用层只依赖 Port Protocol（IdentityUnitOfWork、Repository、AuditPort、OutboxPort），由 Composition Root 注入 `InMemoryUnitOfWork`（测试）或 `SqlAlchemyUnitOfWork`（生产），所有用例共用同一逻辑。

不修改已提交 Alembic `20260712_0001`；如需结构性变更，新增 `20260712_0002_*`。`lifespan` 不得调用 `Base.metadata.create_all`；所有环境只经 `alembic upgrade head`。

审计哈希链使用 `audit.chain_heads` 行锁记录"当前最后哈希"；同事务事件以 `SELECT ... FOR UPDATE` 取链头后再追加，保证 A→B→C 顺序且并发安全。Refresh 用 `FOR UPDATE` 锁定 Family 行保证并发轮换与重放撤销。OAuth Client 启动注册必须多 Pod 幂等（`INSERT ... ON CONFLICT DO NOTHING` 或先查后插）。Redis 降级测试使用抛异常的 `CachePort`，不依赖网络超时。`database_required` 删除。

## Phase / Slice & 合同

- Phase / Slice：Phase 3B Slice 2（IN_PROGRESS）。
- Primary Module：`health_platform.modules.identity`（应用服务 + Port）；Platform / Database、Platform / Security、Platform / Configuration 共同支撑 Composition Root；`health_platform.modules.audit` 扩展 `chain_heads` 与行锁写入。
- 依据 ADR：0018（模块化单体 / Composition Root）、0019（持久化与事务）、0020（Identity 安全）、0021（缓存与后台线程）。
- 依据权威：`docs/SYSTEM_ARCHITECTURE.md`、`docs/DOMAIN_MODEL.md`、`docs/SECURITY_AND_PRIVACY.md`、`docs/API_CONTRACTS.md`、`docs/PHASE_STATUS.md`。
- Allowed Paths：`health_platform/src/health_platform/platform/database/**`、`health_platform/src/health_platform/platform/configuration/**`、`health_platform/src/health_platform/platform/security/cache.py`、`health_platform/src/health_platform/modules/identity/**`、`health_platform/src/health_platform/modules/audit/**`、`health_platform/src/health_platform/platform/web/app.py`、`health_platform/tests/**`、`health_platform/pyproject.toml`、`health_platform/alembic.ini`、`health_platform/migrations/**`、`docs/**`。
- Forbidden Paths：`health_agent/**`、`clients/**`、`frontend/**`、`deploy/**`、删改 `uv.lock`、删改 `migrations/versions/20260712_0001_*`。
- Contract Changes：无（API 路径、OpenAPI、错误模型、客户端行为保持不变）。
- Migration / Compatibility：
  - `Settings.identity_storage` 仅 `"sql"`（移除内存分支）；`local`/`test` 环境也走 SQL，但通过注入 `InMemoryUnitOfWork` 适配应用层。
  - 既有 30 项单元测试改为注入 `InMemoryUnitOfWork` + `InMemoryIdentityRepositories` + `InMemoryAuditRepository` + `InMemoryOutboxRepository`，不再依赖 `IdentityState`。
  - `IdentityState` 保留为 `InMemoryUnitOfWork` 的内部实现细节，不再作为 `IdentityService` 字段。
  - `IdentityError` 等领域 dataclass、API 行为、HTTP DTO 保持。
  - 新增 `migrations/versions/20260712_0002_audit_chain_heads_and_oauth_idempotent.py`，含 `audit.chain_heads` 表 + 触发器 + OAuth 幂等索引。
- Required Verification：`ruff check`、`ruff format --check`、`mypy --no-incremental`、`pytest -m "not postgres" -v`、`pytest -m postgres -v`、`bandit -r src -q`、`pip-audit -r deps`、`cd health_agent && python -m unittest discover -s tests -v`、`alembic upgrade head` 在 PG 集成测试入口自动执行。
- Out of Scope：权限 API、OAuthLib / Client Credentials 完整闭环、邮件 Outbox Processor、OTel 接线、Redis 限流、MFA 关闭 / 重置、固定安全问题、并发幂等业务规则扩展、删改 `uv.lock`、删改 `20260712_0001` 迁移。
- Definition of Done：
  1. 生产 Composition Root 装配 Engine + SessionFactory + SqlAlchemyUnitOfWork + 全部 Repository/Audit/Outbox Port，并通过构造器注入 IdentityService。
  2. IdentityService 不再持有 `self.state`；所有用例统一走 `IdentityUnitOfWork` 抽象；测试用 `InMemoryUnitOfWork`，生产用 `SqlAlchemyUnitOfWork`。
  3. 注册、登录、邮箱验证、Access/Refresh Token、Session 查询与撤销全部走 PostgreSQL；Audit/Outbox/chain_heads 与业务数据同事务；Repository / Router 不 commit；事务内禁止 Redis/SMTP/HTTP。
  4. 5 项新 PostgreSQL 集成测试 + 现有 4 项共 9 项 PG 测试均通过；本地单元测试（注入 InMemory UoW）全过；health-agent 376 项回归仍全过；Mypy / Ruff / Bandit / pip-audit 全通过。
  5. PHASE_STATUS + 实施记录 + Feature Matrix 写入真实证据；Slice 2 与 Phase 3B 仍 `IN_PROGRESS`。

## Current State Analysis

已落地：

- `platform/database/core.py` 已提供 `Base`、`create_database_engine`、`create_session_factory`、`SqlAlchemyUnitOfWork`（含 `set_security_context` 与事务级清理）。
- `modules/identity/adapters/persistence.py` 已建 9 张表（`users / sessions / access_tokens / token_families / refresh_tokens / one_time_tokens / mfa_enrollments / recovery_codes / oauth_clients / jobs / security_events / idempotency_records`），仅 `SqlUserRepository` 实现，其余表未实现 Repository。
- `modules/audit/adapters/persistence.py` 已建 `AuditEventRow` / `OutboxEventRow` 与 `SqlAuditRepository` / `SqlOutboxRepository`，含 `FOR UPDATE SKIP LOCKED` 抢占与锁过期恢复。
- Alembic 单一主线 `20260712_0001` 启用 `identity / audit` Schema、RLS 与审计追加触发器；空库升级 1 head。
- `IdentityService` 仍以 `IdentityState`（纯内存 dict）为权威；`register / login / refresh / verify_email / revoke_session / enroll_mfa / confirm_mfa / recover_mfa / request_password_reset / complete_password_reset / request_export / request_deletion / authorize / exchange_authorization_code` 全部读写 `self.state`，未走 UoW。
- `platform/web/app.py` 仅在 `create_app` 中以 `IdentityService(state=IdentityState())` 装配内存实现；未读取 `settings.database_url`，未连接 Postgres，未启动 Engine。
- 现有 4 项 PG 集成测试在 `test_postgres_integration.py` 仅验证 Schema 与 Outbox 抢占，未覆盖 Identity 业务用例。

缺口：

1. **无生产 Composition Root**：未根据 `Settings.environment` 选择 SQL 或内存，未在生产装配 Engine + SessionFactory + UoW。
2. **Identity 业务用例未走 SQL**：13 个用例直接读写 `self.state.users / .sessions / .families / .access_grants / .one_time_grants / .mfa / .authorization_grants / .oauth_clients / .audits / .outbox`。
3. **缺 Repository**：`sessions / access_tokens / token_families / refresh_tokens / one_time_tokens / mfa_enrollments / recovery_codes / oauth_clients / jobs / authorization_grants` 均无 `Sql*Repository`，无法支持 IdentityService 走 SQL。
4. **Audit 哈希链缺少并发保护**：当前 `IdentityService._audit` 直接读 `self.state.audits[-1].event_hash`，无法在多 Pod / 多请求并发下保证 A→B→C 单调。
5. **配置未启用数据库强校验**：当前 `Settings.validate_production_secrets` 未要求 `database_url` 指向真实 Postgres，未在生产拒绝 `identity_storage != "sql"`。
6. **缺真实 Redis 故障回退测试**：当前 `NullCache` 模拟不能覆盖真实 Redis 抛异常场景；测试需使用抛异常 CachePort。
7. **缺 Refresh 并发轮换与重启后保留的集成测试**：现有 PG 测试不验证 IdentityService 行为。
8. **OAuth Client 启动注册非幂等**：当前 `_register_default_oauth_clients` 在多 Pod 并发首次启动时会重复插入。

## Proposed Changes

### 1. `modules/identity/application/ports.py`（新文件）

定义 Port Protocol（应用层只依赖这些抽象，不依赖 SQLAlchemy / dict 实现）：

```python
class IdentityUnitOfWork(Protocol):
    users: UserRepository
    sessions: SessionRepository
    access_tokens: AccessTokenRepository
    token_families: TokenFamilyRepository
    refresh_tokens: RefreshTokenRepository
    one_time_tokens: OneTimeTokenRepository
    mfa: MfaRepository
    oauth_clients: OAuthClientRepository
    authorization_grants: AuthorizationGrantRepository
    jobs: JobRepository
    deletion_requests: DeletionRequestRepository
    audit: AuditPort
    outbox: OutboxPort
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def __enter__(self) -> "IdentityUnitOfWork": ...
    def __exit__(self, *exc: object) -> None: ...
    def set_security_context(self, user_id: UUID | None, actor_kind: str) -> None: ...
    def run_after_commit(self, hook: Callable[[], object]) -> None: ...
```

每个 Repository Protocol 只暴露业务所需方法（如 `UserRepository.add / get / get_by_identifier / save / list`），不暴露 SQLAlchemy `Session`。`AuditPort.append(event, *, previous_hash)` 返回最终确定的 `event_hash`；`OutboxPort.enqueue(event)` 入队。`run_after_commit` 用于延迟 Redis 失效、SMTP 触发等事务后副作用。

### 2. `modules/identity/application/in_memory_uow.py`（新文件）

- `InMemoryUnitOfWork` 实现 `IdentityUnitOfWork`。
- 内部以 `InMemoryIdentityRepositories` 字典 + 列表保存用户、会话、Family、Token、OneTime、MFA、OAuth Client、Authorization Grant、Job、Deletion、Audit、Outbox；不持久化但保留 `_audit_chain_head` 单变量作为 `previous_hash`。
- `commit()` 触发 `run_after_commit` hooks；`rollback()` 清空待执行 hooks。
- 单元测试改注入此实现，不再使用 `IdentityState`。

### 3. `modules/identity/application/service.py`

- 删除 `IdentityState` 与 `self.state`；所有用例签名保持不变（HTTP 不变）。
- `__init__(passwords, encryption, token_pepper, uow_factory, cache=None, access_ttl, refresh_ttl)`：构造器只保存依赖，不持有任何状态。`uow_factory: Callable[[], IdentityUnitOfWork]`。
- 新增 helper：
  - `_write(actor_kind: str, actor_user_id: UUID | None, fn: Callable[[IdentityUnitOfWork], T]) -> T`：进入 UoW → 设置 `set_security_context` → 调用 `fn(uow)` → `commit()` → 执行 `run_after_commit` hooks → 返回。异常时 `rollback()` 并重抛。
  - `_read(fn)`：进入只读 UoW（不强制 commit），调用 `fn(uow)`，返回；测试中 InMemory UoW 可用 `with` 块。
- `_audit`：改为接受 `IdentityUnitOfWork`，通过 `uow.audit.append(event, previous_hash=uow.audit.current_hash())`；`previous_hash` 由 UoW 内部提供。
- 13 个写用例全部改走 `_write`：
  - 注册：UoW 内 `users.add` + `one_time_tokens.add` + `audit.append` + `outbox.enqueue`。
  - 登录：`users.get_by_identifier` → 校验 → `sessions.add` + `token_families.add` + `refresh_tokens.add` + `access_tokens.add` + `audit.append` + `outbox.enqueue`；`commit()` 后通过 `run_after_commit` 调用 `cache.set`。
  - 刷新：`token_families.lock_for_update(family_id)` → `refresh_tokens.consume` → `access_tokens.add` + `refresh_tokens.add` + `audit.append`；重放时 Family 改 `REPLAY_COMPROMISED`，并 `audit.append BLOCKED` + `outbox.enqueue identity.high_risk_security_event`。
  - 验证 / MFA / 恢复 / 密码重置 / 注销 / 导出 / 授权码 / 兑换授权码：同样 `_write` 模式。
  - `authenticate` 走只读 UoW（`_read`）；命中数据库 access_token 后通过 `run_after_commit` 写入缓存。
- 删除 `self.state.users / .sessions / .families / .access_grants / .one_time_grants / .mfa / .authorization_grants / .oauth_clients / .audits / .outbox / .deletion_requests` 全部字段。
- 兼容处理：原 30 项单元测试 fixture 改为 `uow_factory=lambda: InMemoryUnitOfWork()`，调用断言改为读 UoW 内部 Repository / Audit / Outbox。提供 `tests/conftest.py` 适配。
- 内部数据形状（`UserAccount` / `IdentitySession` / `TokenFamily` / `AccessGrant` / `OneTimeGrant` / `MfaState` / `OAuthClient` / `AuthorizationGrant` / `AccountDeletionRequest`）保持 dataclass，InMemory 与 SQL Repository 各自实现双向 mapper。

### 4. `modules/identity/interfaces/http.py`

- 业务逻辑全部委托 `IdentityService`，不修改路径、DTO、错误模型。
- 仅在调用方需要返回 `AccessGrant` 等 dataclass 时改为通过 Service 的新返回类型（仍转 dict）。

### 5. `platform/database/core.py`

- 保留 `Base` / `create_database_engine` / `create_session_factory` / `SqlAlchemyUnitOfWork`。
- `SqlAlchemyUnitOfWork` 改为实现 `IdentityUnitOfWork` Protocol；提供 `commit / rollback / __enter__ / __exit__ / set_security_context / run_after_commit`。
- 不删除既有签名，仅扩展。
- **禁止** 任何代码在运行时调用 `Base.metadata.create_all`；`lifespan` 中改为 `if settings.environment == "local" and settings.alembic_head_missing:` 仅做健康提示，不执行 DDL。

### 6. `platform/database/sqlalchemy_uow.py`（新文件）

- 把 SqlAlchemy 实现从 `core.py` 抽出独立模块，构造 `SqlUserRepository` / `SqlSessionRepository` / ... / `SqlAuditRepository` / `SqlOutboxRepository` 等实例并绑定到 UoW。
- `SqlUserRepository` 等由 `modules/identity/adapters/persistence.py` 现有文件扩展（新增类）；`platform/database/` 不引入 Identity dataclass，避免反向依赖。

### 7. `modules/identity/adapters/persistence.py`

扩展现有 Repository 实现 + 新增 Repository 类（全部接收 `Session`，不 commit，不远程 I/O）：

- `SqlSessionRepository`
- `SqlAccessTokenRepository`
- `SqlTokenFamilyRepository`：含 `lock_for_update(family_id) -> TokenFamily` 使用 `SELECT ... FOR UPDATE`。
- `SqlRefreshTokenRepository`：含 `consume(presented_hash, new_row)`。
- `SqlOneTimeTokenRepository`：含 `consume(token, kind)`。
- `SqlMfaRepository`
- `SqlOAuthClientRepository`：含 `upsert(client)` 使用 `INSERT ... ON CONFLICT (client_id) DO NOTHING`，多 Pod 幂等。
- `SqlAuthorizationGrantRepository`
- `SqlJobRepository`
- `SqlDeletionRequestRepository`

所有方法返回领域 dataclass，不暴露 ORM 行；与 `SqlUserRepository._to_domain` 风格一致。

### 8. `modules/audit/adapters/persistence.py`

- 新增 `audit.chain_heads` 表模型（`schema="audit"`，单行 `kind VARCHAR PK, last_hash VARCHAR, updated_at TIMESTAMPTZ`）。
- 新增 `SqlChainHeadRepository`：
  - `current(kind: str = "audit_events") -> str`：返回当前链头哈希；缺链头返回 `"GENESIS"`。
  - `advance(kind: str, new_hash: str) -> None`：在 UoW 内 `SELECT ... FOR UPDATE` 锁定 `kind=audit_events` 行，更新 `last_hash = new_hash`、`updated_at = now()`。`FOR UPDATE` 保证并发 `append` 串行化。
- `SqlAuditRepository.append(event)` 改为调用 `chain_heads.advance(...)`：从 `chain_heads.current()` 取 `previous_hash`，写入 `audit.events`，调用 `chain_heads.advance(new_hash)`，最终返回 `event_hash`。
- 单元测试可注入 `InMemoryChainHeadRepository`（保留 InMemory UoW 行为）。

### 9. `migrations/versions/20260712_0002_audit_chain_heads_and_oauth_idempotent.py`（新文件）

- 新增 `audit.chain_heads` 表 + 初始化 `('audit_events', 'GENESIS', now())`。
- 新增 `oauth_clients` 唯一约束（已存在 primary key，不重复）。
- 不修改 `20260712_0001`；新迁移可独立 `upgrade` / `downgrade`。
- 同时新增 `audit_events.previous_hash` 索引以加速查询。

### 10. `platform/configuration/settings.py`

- 新增字段：`identity_storage: Literal["sql"] = "sql"`（**仅 `"sql"`**；移除内存选项以避免双分支）。
- 删除 `database_required`。
- `validate_production_secrets` 中追加：
  - `database_url` 必须以 `postgresql+psycopg://` 开头，否则 `ValueError`。
  - `oidc_current_kid` 必填。
  - `encryption_key_file`、`oidc_private_key_file` 既有校验保持。
- 不在 `Settings` 暴露 InMemory/SQL 切换；测试通过构造器注入 UoW 即可。

### 11. `platform/web/app.py`

- `create_app` 在所有环境下装配 Engine + SessionFactory + `SqlAlchemyUnitOfWork` + 全部 Repository（生产/staging/local/test）；仅 test fixture 可通过参数注入 `uow_factory`。
- `lifespan` 中**禁止**调用 `Base.metadata.create_all`；改为记录 `alembic_version` 表当前 head 与代码期望 head，差异时记 warning，不阻塞启动。
- 缺少 `database_url` 或生产环境关键 Secret 缺失直接抛 `RuntimeError`。
- 装配 `IdentityService(uow_factory=lambda: SqlAlchemyUnitOfWork(...))`；`_register_default_oauth_clients` 改为在 `__init__` 中通过 `IdentityService.ensure_oauth_clients(...)` 使用 `SqlOAuthClientRepository.upsert`，多 Pod 并发幂等。
- Redis 缓存默认 `RedisAuthCache(Redis.from_url(cfg.redis_url, decode_responses=True))` 当 `redis_enabled=True`；否则 `NullCache`。
- JWT key、Probe、lifespan、include_router 不变。

### 12. `platform/security/cache.py`

- 既有 `RedisAuthCache` 与 `NullCache` 保留。
- 新增 `ExceptionRaisingCache`（仅测试用）：`get / set / delete` 全部抛 `RedisError`，用于 Redis 故障回退测试。

### 13. 测试（`tests/test_postgres_integration.py` + `tests/test_identity_postgres.py` + `tests/test_in_memory_uow.py`）

5 项新真实 PG 集成测试（全部 `@pytest.mark.postgres`）：

1. **重启后数据保留**：注册账号 → 关闭 Session/Engine → 新 Engine 重建 Session → 通过 `IdentityService.authenticate` 用同一 Access Token 命中。
2. **事务回滚**：注册成功用例中，`SqlOutboxRepository.enqueue` 抛 `IntegrityError`（注入错误 Repository 实现）模拟 commit 前失败，验证 `identity.users` / `audit.events` / `audit.outbox_events` 均未写入。
3. **审计原子性与并发链头**：并行启动 N=8 协程注册不同账号，验证 `audit.events.previous_hash` 形成 A→B→C 单链；所有 `event_hash` 唯一。
4. **Refresh 并发轮换**：同 Family 同一 Refresh Token 两个并发请求（线程），一个成功返回新 Token，另一个触发 `IDENTITY_REFRESH_TOKEN_REPLAY`，Family 终态 `REPLAY_COMPROMISED`，所有 `access_tokens` 被撤销。
5. **Redis 故障回退**：装配 `ExceptionRaisingCache`；`authenticate` 仍能从 PostgreSQL 命中 Access Token 并返回正确 `AccessGrant`。

辅助：

- `tests/conftest.py` 提供 `postgres_url` / `migrated_engine` / `identity_service_factory` / `uow_factory`，被新旧 PG 测试共享；既有 4 项 PG 测试改用同一 fixture，不重复 `PostgresContainer`。
- `tests/test_in_memory_uow.py` 新增单元测试覆盖 `InMemoryUnitOfWork` + InMemory Audit/Outbox 的语义对等（事务、commit hooks、回滚）。

### 14. Feature Matrix 与 PHASE_STATUS

- `docs/design/health-platform/FEATURE_MATRIX.md` 把 Identity 行的状态从「内存实现」更新为「SQL Composition Root 已注入；InMemory UoW 仅测试；生产单一路径走 PostgreSQL」。
- `docs/PHASE_STATUS.md` 在 Slice 2 段下追加 "SQL Composition Root (本轮)" 段：列出真实命令、实际命令输出、9 项 PG 测试编号、`alembic upgrade head` 在测试 fixture 中执行的真实证据、未验证项与 Slice 2 / Phase 3B 仍 `IN_PROGRESS`。

## Assumptions & Decisions

1. **应用层不再持有状态**：`IdentityService` 仅保存构造器依赖；所有状态读写经 `IdentityUnitOfWork`。InMemory 与 SQL 两个实现共享同一接口语义。
2. **审计链头表行锁**：`audit.chain_heads` 单行 `kind='audit_events'`；`append` 流程为 `current() → INSERT audit.events → advance(new_hash)`，全程在 UoW 内；并发请求通过 `FOR UPDATE` 排队，保证 `previous_hash` 单调。
3. **OAuth Client 幂等**：`SqlOAuthClientRepository.upsert` 使用 `INSERT ... ON CONFLICT (client_id) DO NOTHING`；Composition Root 启动时对每个默认 client 调一次。多 Pod 并发启动最终一致。
4. **Refresh 并发**：Family 行用 `FOR UPDATE`；重放请求读到 Family 状态 `REVOKED` 时直接抛 `IDENTITY_INVALID_REFRESH_TOKEN`；新请求读到 `ACTIVE` 时继续轮换。
5. **Redis 故障**：`RedisAuthCache` / `NullCache` / 测试用 `ExceptionRaisingCache` 共用 `CachePort` Protocol；应用层在 cache 抛异常时记 warning 并继续走数据库。
6. **Unit tests 全部走 InMemoryUoW**：fixture 改为 `IdentityService(uow_factory=lambda: InMemoryUnitOfWork(), cache=None)`；HTTP / 接口测试继续用 FastAPI TestClient 但底层是 InMemoryUoW，不依赖 Postgres。
7. **测试用 Alembic 升级**：`tests/conftest.py` 在创建 `PostgresContainer` 后调用 `alembic upgrade head`，验证 `0001 + 0002` 一起生效；不再依赖 `Base.metadata.create_all`。
8. **不修改 `uv.lock`**：`uv sync --frozen --all-packages` 保持；`sqlalchemy`/`psycopg[binary]`/`alembic`/`pydantic-settings` 已在。
9. **不实现 Outbox 后台发送**：本 Slice 只保证 `outbox.enqueue` 在同事务写入；`BackgroundWorker` 真实消费由后续 Slice 完成；现有 `recover_expired / claim / mark_published / mark_failed` 接口保留。
10. **不引入 Permission RBAC 管理端点**：留待后续 Slice。

## Verification

按顺序执行并记录真实输出：

```bash
# 静态
.venv/bin/ruff format --check health_platform/src/health_platform health_platform/tests
.venv/bin/ruff check health_platform/src/health_platform health_platform/tests
.venv/bin/mypy --no-incremental health_platform/src/health_platform

# 单元 / 应用（InMemoryUoW）
.venv/bin/python -m pytest health_platform/tests -m "not postgres" -v

# PostgreSQL 集成（含 5 项新测试 + 4 项既有）
.venv/bin/python -m pytest health_platform/tests -m postgres -v

# 安全
.venv/bin/bandit -r health_platform/src/health_platform -q
.venv/bin/pip-audit -r <dependencies>

# Alembic 验证
cd health_platform && alembic upgrade head && alembic check

# health-agent 回归
cd health_agent && python3 -m unittest discover -s tests -v

# git hygiene
git diff --check
```

## Risk & Open Questions

- **Testcontainers 端口探测异常** 仍 BLOCKED；若 PG 集成测试再次失败，遵守"不修改业务代码规避"原则，把环境失败事实写入 PHASE_STATUS，不伪造通过。
- **`IdentityService.authenticate` 需要返回 dataclass 给 Router**：HTTP 层访问 `AccessGrant.user_id / .session_id` 等；保持返回类型不变，HTTP 层转 dict。
- **OAuth Client 启动幂等性测试**：需要在并发线程中执行 `ensure_oauth_clients`，验证仅一条记录；多 Pod 行为通过 PostgreSQL 唯一约束保证。
- **审计哈希链测试**：并发 8 协程注册需使用 `concurrent.futures.ThreadPoolExecutor`；每协程独占 UoW（独立 Session），最终通过 `SELECT event_hash, previous_hash FROM audit.events ORDER BY occurred_at` 验证链顺序。
- **回滚测试**：必须模拟"commit 前失败"，通过 Repository 子类化注入 `IntegrityError`；不应触发 commit 后的写入。
- **无新增 HTTP DTO / 路径**：现有 `tests/test_api.py` 4 项需保持原行为；新行为依赖 InMemoryUoW 后断言方式调整为查 `uow.audit.events` / `uow.outbox.events`。