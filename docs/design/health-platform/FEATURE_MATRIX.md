# 功能矩阵

状态仅使用 `DONE / PARTIAL / SKELETON / TODO / BLOCKED`。完成状态以代码和实际验证证据为准。

| Feature | Module | Description | Status | API | Domain Object | Persistence | Security | Audit | Tests | Phase | Out of Scope |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 注册与账号 | identity | 邮箱/用户名、基础档案、唯一性 | PARTIAL | register/me | User | identity.users | Argon2id、规范化 | 是 | 单元/API/PG | 3B | 健康档案 |
| 邮箱验证 | identity | 一次性短期哈希 Token | PARTIAL | verification | EmailVerification | identity.email_verifications | 高熵/轮换 | 是 | 单元/API | 3B | 邮件入站 |
| 登录风控 | identity | 账号/IP/设备退避与锁定 | PARTIAL | login | LoginGuard | user/security event | Redis 降级 DB | 是 | 单元/API | 3B | 风险模型 |
| OAuth/OIDC | identity | Code+PKCE、Client Credentials、Discovery/JWKS | PARTIAL | oauth/oidc | AuthorizationGrant | oauth tables | RS256/S256/nonce | 是 | API/security | 3B | 第三方平台 |
| Token/Session | identity | 不透明 Token、轮换、重放、设备撤销 | PARTIAL | token/sessions | TokenFamily/Session | identity tokens | 哈希/即时撤销 | 是 | 单元/API/PG | 3B | health-agent Run |
| MFA | identity | TOTP 与一次性恢复码 | PARTIAL | mfa | MfaEnrollment | identity mfa | 字段加密/哈希 | 是 | 单元/API | 3B | 短信 MFA |
| 密码恢复 | identity | 邮件 + 固定安全问题辅助 | PARTIAL | recovery | PasswordRecovery | identity recovery | 模糊响应/哈希 | 是 | 单元/API | 3B | 客服改密 |
| RBAC 基础 | identity | 角色、资源归属、关系授权 | PARTIAL | admin foundation | Role/Grant | identity grants | Policy + RLS | 是 | 单元/PG | 3B | Fact/Plan 授权 |
| Audit | audit | 追加审计与哈希链 | PARTIAL | 无公共 API | AuditRecord | audit.events | 禁止敏感字段 | 自身 | 单元/PG | 3B | 审计 UI |
| Outbox/后台 | audit/platform | 抢占、重试、恢复、heartbeat | PARTIAL | probes | OutboxEvent | audit.outbox | 独立事务 | 是 | 单元/PG | 3B | Agent Task Outbox |
| Redis 缓存 | platform | Token/Session 短 TTL 与降级 | PARTIAL | 间接 | CacheEntry | Redis 非权威 | Token 哈希 Key | 指标 | 单元/API | 3B | Redis Streams Agent Queue |
| 加密/密钥 | platform | 版本化 AES-GCM 与 K8s Secret Adapter | PARTIAL | 无公共 API | EncryptedValue | 密文元数据 | current/historical | 是 | 单元 | 3B | Vault/KMS |
| 邮件通知 | identity | SMTP + 开发捕获 + Outbox | PARTIAL | 间接 | Notification | audit.outbox | Secret 隔离 | 是 | 单元 | 3B | 邮件入站 |
| 导出/注销 | identity | 任务框架、7 天冷静期、撤销 | PARTIAL | export/deletion | ExportJob/DeletionRequest | identity tasks | 重认证/MFA | 是 | 单元/API | 3B | 其他模块数据删除 |
| Conversation | conversation | 正式对话业务 | SKELETON | 无 | 无 | 无 | 边界文档 | 否 | 结构检查 | 3D | 本 Slice |
| Fact/Goal/Plan/Risk/File/Secret | modules | 冻结业务模块边界 | SKELETON | 无 | 无 | 无 | 边界文档 | 否 | 结构检查 | 3D–3H | 本 Slice |
| Agent Integration | agent_integration | Platform/Agent 合同边界 | SKELETON | 无 | 无 | 无 | mTLS/JWT 设计 | 否 | 结构检查 | 3C–3D | 本 Slice |
