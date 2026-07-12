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

验证证据：Ruff、Mypy、30 项非 PostgreSQL 测试、85% 覆盖率、4 项 Testcontainers PostgreSQL 测试、Bandit、pip-audit 与 health-agent 376 项回归通过。

未完成：生产 SQL Composition Root；OAuthLib/Client Credentials/完整 Revocation；IP/设备 Redis 限流；MFA 关闭/重置；固定安全问题；权限管理用例；SMTP Outbox Processor；OTel instrumentation；数据库/Alembic readiness；并发 Refresh/幂等和审计不可变集成测试。因此 Slice 2 和 Phase 3B 保持 `IN_PROGRESS`。
