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

未完成（参见 Slice 2 完成记录）：OAuthLib/Client Credentials 完整闭环、Redis IP/设备限流、MFA 关闭/重置、权限管理用例、SMTP Outbox Processor、OTel instrumentation。