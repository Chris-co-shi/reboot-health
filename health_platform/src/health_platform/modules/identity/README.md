# identity 模块

状态：`PARTIAL`（Slice 2 实现中）。

职责：用户身份、不透明 Token、Refresh Token Family、设备会话、MFA、邮箱验证、密码恢复、账号导出/删除、第一方 OAuth/OIDC。

主要位置：

```text
modules/identity/
├── domain/            纯领域模型（UserAccount / IdentitySession / TokenFamily / RecoveryCode / AccountDeletionRequest / IdentityError）
├── application/       IdentityService、OAuthClient、CachePort、IdentityState、TOTP 工具
├── adapters/          SQLAlchemy 持久化模型与 Repository、邮件适配器
├── ports/             EmailPort / EmailMessage
└── interfaces/        Identity HTTP 入口（API 路由、DTO、principal 依赖、IdentityError handler）
```

当前 Slice 已完成：

- `interfaces/http.py` 集中承载 DTO、`principal` Bearer 解析、Identity/OAuth/OIDC 路由；
  `platform/web/app.py` 仅保留 Composition Root、Probe、lifespan 与 `include_router`。
- 全部路由路径、响应结构、状态码与 OpenAPI 与迁移前保持一致。
- 首发人类角色已收敛为 `USER / ADMIN_OPERATOR`；`SERVICE_HEALTH_AGENT` 使用独立 Actor Kind；新增默认拒绝的 Principal Policy，管理员能力强制 MFA。
- 全部 Identity Repository Port 已有显式 Domain/Row 双向 Mapper 和 SQL 实现；生产使用 `SqlAlchemyIdentityUnitOfWork`，Audit/Outbox 与身份状态同事务。
- production Composition Root 不再回退 InMemory；关键数据库、密钥、签名与第一方 OAuth 配置缺失时 fail-closed。
- readiness 验证 PostgreSQL 连接、单 Alembic Head 与当前 revision；不执行 migration 或 `create_all`。

未完成（参见 Slice 2 完成记录）：管理员 Application Use Case、完整 Refresh 并发/重放、OAuthLib/Client Credentials 完整闭环、Redis IP/设备限流、MFA 关闭/重置、SMTP Outbox Processor、OTel instrumentation。
