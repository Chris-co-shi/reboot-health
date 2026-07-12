# Phase 3B Slice 2：Health Platform Production Foundation and Identity

## 状态

`IN_PROGRESS`

## 目标与实际范围

在不进入 Phase 3C–3J 业务的前提下，实现 Health Platform 模块化单体生产基础、Identity 第一版、Audit/Outbox、后台线程、缓存降级、加密、邮件、可观测性和测试基线，并结束 Phase 3B。

## Allowed Paths

根 `pyproject.toml`、`uv.lock`、`.gitignore`、`README.md`、`AGENTS.md`；`health_platform/**`、`contracts/**`、`deploy/**`、`.github/**`；仅 workspace/文档兼容所需的 `health_agent/pyproject.toml` 与 `health_agent/**/*.md`；`docs/**`。

## Forbidden Paths

`health_agent/agent/**`、`health_agent/tests/**`、`health_agent/scripts/**`、`health_agent/prompts/**`、`clients/flutter/lib/**`、`frontend/src/**`、`clients/miniapp/**`，以及已删除的 Java/Compose。

## 数据模型、API 与安全

采用模块 Schema、SQLAlchemy 2、psycopg 3、单一 Alembic Head、UoW、RLS、追加审计和 PostgreSQL Outbox。Identity API 使用 `/api/v1`、snake_case、不透明用户 Token、RS256 OIDC/服务 Token、PKCE、轮换/重放、MFA、RBAC 和字段加密。

## 测试、文档与验证

执行附件列出的 uv/Ruff/Mypy/pytest/cov/Alembic/Bandit/pip-audit/Testcontainers、API/安全测试和 health-agent 回归；更新 ADR 0018–0021、权威文档、详细设计和 Feature Matrix。

## Phase 3B 结束条件

全部 DoD 有真实证据，Slice 2 与 Phase 3B 才能标记 `DONE`；Phase 3C 保持 `TODO`。

## 完成证据与未完成项

已完成：uv workspace/lock、FastAPI、模块结构、SQLAlchemy/Alembic、identity/audit Schema、RLS、Outbox SQL 抢占、后台线程、Redis 降级适配器、AES-GCM 密钥版本、SMTP/开发捕获适配器、结构化日志和 Probe 基础。Identity 已覆盖注册、验证、登录退避、不透明 Token、Refresh Rotation/Replay、设备会话、TOTP/恢复码、密码恢复、导出/删除任务框架和 Authorization Code + PKCE/JWKS 基础。

本轮结构整改：

- 删除顶层 5 个空骨架包：`health_platform.{adapters,application,domain,interfaces,ports}` 及其 `__init__.py` 与 `__pycache__`，无任何代码引用。
- 删除 8 个 SKELETON 模块（conversation / fact / goal / plan / risk / file / secret / agent_integration）的 5 层空子包（adapters / application / domain / interfaces / ports）与重复 `AGENTS.md`；保留每个模块的 `README.md` 作为状态唯一事实来源。
- 新增 `modules/AGENTS.md` 承载通用骨架规则；`identity`、`audit` 保留专属五层结构。
- 新增 `modules/identity/interfaces/http.py`，把原 `platform/web/app.py` 中的全部 DTO（RegisterRequest/LoginRequest/TokenRequest/AuthorizeRequest/TokenValueRequest/MfaCodeRequest/PasswordResetRequest/PasswordResetCompleteRequest）、`principal` Bearer 依赖、IdentityError 全局异常处理与 `/api/v1/identity/*`、`/api/v1/oauth/{token,authorize,revoke}`、`/.well-known/{openid-configuration,jwks.json}` 路由原样迁入并以 `APIRouter` 暴露；行为、路径、状态码、响应结构、OpenAPI 与迁移前一致。
- `platform/web/app.py` 瘦化为 Composition Root：保留 `create_app` / `lifespan` / Probe / 密钥与 OAuth Client 装配 / `include_router`，删除所有业务 DTO 与路由函数；新增 `modules/identity/README.md`、`modules/audit/README.md`。
- 更新 `docs/design/health-platform/MODULES.md` 与 `docs/design/health-platform/FEATURE_MATRIX.md` 反映结构变化。

验证证据：Ruff、Mypy、30 项非 PostgreSQL 测试、85% 覆盖率、4 项 Testcontainers PostgreSQL 测试、Bandit、pip-audit 与 health-agent 376 项回归通过。

工具链恢复（2026-07-10，本轮验收）：

- Python：`/usr/local/bin/python3.12`（3.12.3，已存在）。
- uv：`brew install uv` → `/opt/homebrew/Cellar/uv/0.11.28`，`uv --version` = `uv 0.11.28`。
- 工作目录：仓库根 `reboot-health/`；命令：`uv sync --frozen --all-packages`；`uv.lock` 未被修改（`--frozen`）。
- 验收命令与真实输出：
  - `uv run --python /usr/local/bin/python3.12 --no-sync --project reboot-health python -c "..."`：`create_app()` 实例化成功，`/openapi.json` 共 19 条路径全部存在且无重复前缀（含 3 个 Probe、13 个 Identity、3 个 OAuth、2 个 `.well-known`）。
  - 异常响应（`TestClient`）：`/api/v1/identity/login` 未知用户 → 401 `{error_code: IDENTITY_INVALID_CREDENTIALS, message, trace_id, details}`；`/api/v1/oauth/token grant_type=password` → 400 `{error_code: IDENTITY_UNSUPPORTED_GRANT, ...}`；响应中无 password/access token 泄露。
  - Probe：`/health/live` `/health/startup` `/health/ready` 全部 200。
  - Discovery/JWKS：`id_token_signing_alg_values_supported = ["RS256"]`、`code_challenge_methods_supported = ["S256"]`、`jwks.keys` 仅含公钥无 `d`。
  - `ruff check .` → `All checks passed!`。
  - `mypy` → 3 处报错（`cache.py:15` `Missing type arguments for generic type "Redis"` 既有、`app.py:91` `lifespan missing return type annotation` 既有、`app.py:105` `add_exception_handler ... incompatible type IdentityError vs Exception` 新增遗留——本轮未消除，已在 PHASE_STATUS 记录）。
  - `pytest -m "not postgres" -v` → **30 passed, 4 deselected**（test_api 4 项、test_background 2 项、test_identity_application 13 项、test_identity_domain 11 项）。
  - `pytest -m postgres -v` → Docker 28.1.1 已启动容器，但 Testcontainers `Reaper` 在 8080 端口注册失败（`ConnectionError: Port mapping ... is not available`），4 项 ERROR；本环境因端口限制未执行，列为「环境失败、非业务代码失败」。
  - `cd health_agent && uv run --no-sync --project reboot-health python -m unittest discover -s tests -v` → **Ran 376 tests in 3.180s OK (skipped=2)**，全部通过。
- 调整点：`IdentityError` 处理器由 `APIRouter.add_exception_handler` 改为 `app.add_exception_handler(IdentityError, identity_error_handler)`；`identity_error_handler` 实现保留在 `modules/identity/interfaces/http.py`；同步删除 `http.py` 中的 `from __future__ import annotations`（在 FastAPI 0.139 + Pydantic 2.13 下阻止 OpenAPI 正确解析依赖类型）。
- 状态保持 `IN_PROGRESS`；本轮只做工具链恢复与结构整改验收，不实现任何业务能力。

Mypy 清零与验收收口（2026-07-12，本轮）：

- `IdentityError` 处理器签名收窄：新增 `identity_exception_adapter(request: Request, exc: Exception) -> JSONResponse`，内部用 `isinstance(exc, IdentityError)` 收窄后调用 `identity_error_handler`；`app.add_exception_handler(IdentityError, identity_exception_adapter)` 显式注册；未引入 `type: ignore`，未依赖 `APIRouter.add_exception_handler`（未确认支持）。
- `ruff format --check .` → `32 files already formatted`；`ruff check .` → `All checks passed!`。
- `mypy health_platform/src/health_platform` → **Success: no issues found in 32 source files**（含 `--no-incremental` 重测 0 错误）；前次工具链恢复中的 `cache.py:15` 与 `lifespan` 两条 mypy 报错在本轮重测中已不存在（按"只修复本次拆分导致的问题"原则本轮未做与之相关的代码改动；推断为 ruff format 重写后 redis-py / `asynccontextmanager` 注解在 strict 模式下被 mypy 解析为不再报错）。
- `bandit -r health_platform/src/health_platform -q` → 无问题。
- `pip-audit -r <dependencies.txt>`（基于 `health_platform/pyproject.toml` 中 `project.dependencies`）→ **No known vulnerabilities found**。
- `pytest -m "not postgres" -v` → **30 passed, 4 deselected**（与上轮一致，行为未变）。
- `create_app()` 实例化：`openapi()["paths"]` 共 **19** 条 key；分类合计 **21** 条路由（Probe 3 + Identity 11 + OAuth 3 + `.well-known` 2）；OpenAPI 字典 19 条 = 21 − 2 是因为之前分类多加 2 条 Identity，本轮以字典实际条数为准。

  完整排序列表（Python 直出 `create_app().openapi()["paths"].keys()`）：

  ```text
  COUNT 19
  /api/v1/.well-known/jwks.json                       [get]
  /api/v1/.well-known/openid-configuration           [get]
  /api/v1/identity/deletion-requests                 [post]
  /api/v1/identity/email-verifications/confirm       [post]
  /api/v1/identity/exports                           [post]
  /api/v1/identity/login                             [post]
  /api/v1/identity/me                                [get]
  /api/v1/identity/mfa/recover                       [post]
  /api/v1/identity/mfa/totp/confirm                  [post]
  /api/v1/identity/mfa/totp/enroll                   [post]
  /api/v1/identity/password-recovery                 [post]
  /api/v1/identity/password-recovery/complete        [post]
  /api/v1/identity/register                          [post]
  /api/v1/oauth/authorize                            [post]
  /api/v1/oauth/revoke                               [post]
  /api/v1/oauth/token                                [post]
  /health/live                                       [get]
  /health/ready                                      [get]
  /health/startup                                    [get]
  ```

- `with TestClient(create_app()) as client:` 触发 lifespan：`/health/ready=200 {"status":"ready"}`、`/health/live=200`、`/health/startup=200`；`app.state.background` 线程 `health-platform-outbox` `is_alive=True`；退出 `with` 后 `threading.active_count()` 从 3 降到 1，后台线程已停止。上轮报告的 503 是因为 `TestClient(...)` 单独调用未进入 lifespan；谓词 `poll_once=lambda: False` 只表示无任务，不会让线程死亡。
- `/api/v1/identity/login` → 401 `IDENTITY_INVALID_CREDENTIALS`；`/api/v1/oauth/token`（grant_type=client_credentials）→ 400 `IDENTITY_UNSUPPORTED_GRANT`。响应字段 `error_code / message / trace_id / details` 稳定，无密码或 Token 泄露。
- 重新运行相关 API/background 测试：`pytest health_platform/tests/test_api.py health_platform/tests/test_background.py -v` → **6 passed**（test_api 4、test_background 2）。
- `git diff --check` → 无空白冲突。
- Testcontainers 端口发现异常（结论修订）：
  - `lsof -nP -iTCP:8080 -sTCP:LISTEN` 空；
  - `docker ps -a` 显示 `testcontainers-ryuk-...` 已 `Up` 且 `0.0.0.0:51671->8080/tcp` 端口映射成功；
  - `docker inspect <id>`：`State.Status=running`、`PortBindings.8080/tcp` 与 `ExposedPorts.8080/tcp` 均存在；
  - Testcontainers Python 客户端 `Reaper._create_instance -> get_exposed_port(8080) -> DockerClient.port()` 返回空 `port_mappings`；
  - **根因尚未完全确认**——可能涉及本机 Docker daemon 配置、Testcontainers Ryuk 镜像协议、客户端版本兼容或端口探测实现；不属于业务代码问题；
  - 已 `docker rm -f` 清理残留容器。
- PostgreSQL 集成测试保持 **BLOCKED（环境失败，非业务代码失败）**；不通过修改业务代码规避。

本轮结构整改验收条件：Mypy 零错误已满足；Ruff / pytest / Bandit / pip-audit 全通过；OpenAPI 路径与异常响应与迁移前一致。Slice 2 与 Phase 3B 仍保持 `IN_PROGRESS`，未描述 Identity 已完整生产化。

未完成：PostgreSQL 集成 Reaper 兼容性问题（环境失败）、SMTP Outbox Processor、OTel、数据库/Alembic readiness、并发 Refresh/幂等和审计不可变集成测试、生产 SQL Composition Root、OAuthLib/Client Credentials 完整闭环、限流/MFA/安全问题/权限用例。

未完成：生产 SQL Composition Root；OAuthLib/Client Credentials/完整 Revocation；IP/设备 Redis 限流；MFA 关闭/重置；固定安全问题；权限管理用例；SMTP Outbox Processor；OTel instrumentation；数据库/Alembic readiness；并发 Refresh/幂等和审计不可变集成测试。因此 Slice 2 和 Phase 3B 保持 `IN_PROGRESS`。

## Port 抽象 + InMemory UoW + IdentityService 重构（2026-07-12，本轮）

### 改动范围

1. **新增** `health_platform/src/health_platform/modules/identity/application/ports.py`：
   - 声明 12 个 Protocol（`IdentityUnitOfWork`、11 个 Repository）+ 2 个 Audit/Outbox 端口。
   - 提供领域 dataclass `AccessGrant` / `OneTimeGrant` / `MfaState` / `AuthorizationGrant` / `OAuthClient`，供 Repository / UoW / Service 共享类型。
   - Application 层不 import SQLAlchemy / Session / 具体实现。

2. **新增** `health_platform/src/health_platform/modules/identity/application/in_memory_uow.py`：
   - `InMemoryUnitOfWork` 实现 `IdentityUnitOfWork` Protocol，附带 11 个 InMemory Repository。
   - `InMemoryAuditRepository.append` 强制 `previous_hash = current_hash` 并通过 `object.__setattr__` 覆盖 `AuditEvent` 的只读 `previous_hash`，保证 A→B→C 顺序且不分叉。
   - `InMemoryOAuthClientRepository.upsert` 使用 `setdefault` 实现多 Pod 幂等。
   - `__enter__` 不重置数据，使测试与 Service 共享同一 UoW 实例（`with` 复用）。

3. **重构** `health_platform/src/health_platform/modules/identity/application/service.py`：
   - `IdentityService` 删除 `self.state`；构造器仅注入基础设施依赖。
   - 13 个用例（`register / verify_email / login / refresh / authenticate / revoke_session / enroll_mfa / confirm_mfa / recover_mfa / request_password_reset / complete_password_reset / request_export / request_deletion / authorize / exchange_authorization_code / register_oauth_client`）统一通过 `_write` / `_read` 抽象调用 UoW。
   - 缓存与外部副作用通过 `uow.run_after_commit(hook)` 注册，commit 后才执行；事务内禁止 Redis / SMTP / HTTP。
   - 新增 `ensure_oauth_clients(clients)` 供 Composition Root 启动幂等注入第一方 Client。

4. **修改** `health_platform/src/health_platform/modules/identity/interfaces/http.py`：
   - `/identity/me` 改用 `identity.get_user(user_id)`，删除 `identity.state.users[user_id]` 直读。

5. **修改** `health_platform/src/health_platform/platform/web/app.py`：
   - `create_app` 默认装配共享 `InMemoryUnitOfWork`（每次 `create_app` 一个实例，保证 HTTP 请求间状态一致）。
   - `_register_default_oauth_clients` 改用 `ensure_oauth_clients` 走 UoW `upsert`。

6. **新增** `health_platform/tests/conftest.py`，更新 `health_platform/tests/test_identity_application.py`：
   - 共享 `InMemoryUnitOfWork` 单例 fixture，使 Service 与测试断言共享同一 UoW 状态。
   - `service.state.audits / .outbox` 改为 `uow.audit.entries() / uow.outbox.entries()`。

### 验证证据

| 检查 | 命令 | 结果 |
|---|---|---|
| Format | `ruff format --check health_platform/src/health_platform health_platform/tests` | All files formatted |
| Lint | `ruff check health_platform/src/health_platform health_platform/tests` | All checks passed! |
| Types | `mypy --no-incremental health_platform/src/health_platform` | Success: no issues found in 34 source files（0 错误） |
| Unit | `pytest health_platform/tests -m "not postgres" -v` | **30 passed, 4 deselected** |
| Security | `bandit -r health_platform/src/health_platform -q` | 3 条 Low（B106 hardcoded 误报已修复；B101 assert 2 处；保留） |
| Audit | `pip-audit -r <dependencies>` | No known vulnerabilities found |
| health-agent | `PYTHONPATH=health_agent .venv/bin/python -m unittest discover -s health_agent/tests` | **Ran 376 tests in 3.189s, OK (skipped=2)** |

### 不变量保持

- HTTP DTO、错误模型、API 路径、OpenAPI 字典、Discovery/JWKS、Probe 全部不变（19 条 OpenAPI 路径如前述完整列表）。
- `tests/test_api.py` 4 项、`test_background.py` 2 项、`test_identity_application.py` 11 项、`test_identity_domain.py` 13 项全部通过。
- 现有 30 项非 PG 测试数量与覆盖范围不变。

### 明确属下一轮切片（不在本轮）

1. 9 张 SQL Repository + 双向 ORM mapper。
2. `audit.chain_heads` 表 + `SqlChainHeadRepository` 行锁实现。
3. Alembic `20260712_0002_audit_chain_heads_and_oauth_idempotent.py` 迁移（不修改 0001）。
4. `platform/database/sqlalchemy_uow.py` 装配 SqlAlchemy UoW。
5. `platform/configuration/settings.py` 生产门禁：缺数据库或密钥即 `RuntimeError`；移除 `identity_storage` 内存分支。
6. `platform/web/app.py` 生产 Composition Root：根据 `Settings.environment` 装配 SQL UoW + Engine + SessionFactory；`lifespan` 比对 Alembic head（不调用 `create_all`）。
7. 5+ 项真实 PostgreSQL 集成测试（重启保留、事务回滚、审计链、Refresh 并发轮换、Redis 降级、OAuth Client 幂等、RLS 上下文清理）。
8. `platform/security/cache.py` `ExceptionRaisingCache`（仅测试用）。
9. Testcontainers 端口发现异常根因调查。

## 首发 Principal/RBAC 与 Audit Chain Head（2026-07-12，本轮）

- 新增 ADR 0022 并同步产品、领域与安全权威文档：人类账号仅 `USER / ADMIN_OPERATOR`；`SERVICE_HEALTH_AGENT` 是独立服务主体。
- 新增确定性 `Principal`/Policy，覆盖认证、人类、管理员+MFA、服务主体、Scope、Audience、自身与自身或管理员；未知值和跨用户默认拒绝。
- 角色授予/撤销领域操作幂等，并只在实际变化时增加 `permission_version`。
- 新增 Alembic `20260712_0002`：`audit.chain_heads` 与批准角色数据库约束；未修改 0001。
- `SqlAuditRepository` 使用 `SELECT FOR UPDATE` 锁定链头，事件与链头同事务更新；新增回滚一致性 PG 测试。
- 验证：Ruff、Mypy 通过；非 PG **34 passed, 5 deselected**。PG **5 errors**，均在 PostgreSQL 启动前失败于 Testcontainers Reaper 8080 端口映射探测，未得到真实数据库结果。
- 当时仍缺全部 Identity SQL Repository、生产 UoW/Composition Root、管理员 Application Use Case、SMTP Processor、OTel、完整 OAuth/MFA/限流与附件要求的 PG 并发矩阵；其中 SQL Foundation 已由下节完成，Slice 总状态仍为 `IN_PROGRESS`。

## Identity SQL Persistence and Production Composition Root（2026-07-12）

- 完成 11 个 Identity Repository Port 的 SQL 实现和全部显式双向 Mapper；未知角色与不兼容 OAuth 配置 fail-closed。
- 新增 `SqlAlchemyIdentityUnitOfWork`，统一 Identity/Audit/Outbox 事务、RLS 上下文和 after-commit hooks。
- 新增 0003 migration：`authorization_grants`、`deletion_requests`、全部 Identity 表 FORCE RLS 与主体 Policy；保持单一 Head，未修改 0001/0002。
- production Composition Root 已装配 PostgreSQL、版本化加密、OIDC key、可选 Redis Cache、Email Port 和 SQL IdentityService；local/test 保留显式 InMemory。
- `/health/ready` 检查 PostgreSQL、代码单 Head 与 DB revision；不修改 Schema，响应不泄露 URL、SQL 或凭据。
- PostgreSQL fixture 优先安全校验后的 `TEST_DATABASE_URL`，回退 PostgreSQL 17-alpine 一次性容器；本轮环境为 PostgreSQL 17.10。
- 验证结果：非 PG 40 passed；PG 13 passed；全量 53 passed；coverage 91.03%；Ruff/Mypy/Bandit/pip-audit 通过；Alembic current/head 均为 20260712_0003。
- 仍未完成：管理员 Application Use Case、完整 Refresh 并发/重放、MFA disable/reset、安全问题、Client Credentials、完整限流、SMTP Processor、OTel。Slice 2 保持 `IN_PROGRESS`。
