# 功能矩阵

状态仅使用 `DONE / PARTIAL / SKELETON / TODO / BLOCKED`。完成状态以代码和实际验证证据为准。

| Feature | Module | Description | Status | API | Domain Object | Persistence | Security | Audit | Tests | Phase | Out of Scope |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 注册与账号 | identity | 邮箱/用户名、基础档案、唯一性 | PARTIAL | register/me | User | identity.users | Argon2id、规范化 | 是 | 单元/API/PG | 3B | 健康档案 |
| Identity HTTP 拆分 | identity/platform | DTO/路由/principal 依赖从 platform/web/app.py 迁至 modules/identity/interfaces/http.py | PARTIAL | 接口迁移 | APIRouter | 无新增 Schema | OpenAPI 不变 | 是 | API | 3B | OAuth 闭环 |
| 邮箱验证 | identity | 一次性短期哈希 Token | PARTIAL | verification | EmailVerification | identity.email_verifications | 高熵/轮换 | 是 | 单元/API | 3B | 邮件入站 |
| 登录风控 | identity | 账号/IP/设备退避与锁定 | PARTIAL | login | LoginGuard | user/security event | Redis 降级 DB | 是 | 单元/API | 3B | 风险模型 |
| OAuth/OIDC | identity | Code+PKCE、Client Credentials、Discovery/JWKS | PARTIAL | oauth/oidc | AuthorizationGrant | oauth tables | RS256/S256/nonce | 是 | API/security | 3B | 第三方平台 |
| Token/Session | identity | 不透明 Token、轮换、重放、设备撤销 | PARTIAL | token/sessions | TokenFamily/Session | identity tokens | 哈希/即时撤销 | 是 | 单元/API/PG | 3B | health-agent Run |
| MFA | identity | TOTP 与一次性恢复码 | PARTIAL | mfa | MfaEnrollment | identity mfa | 字段加密/哈希 | 是 | 单元/API | 3B | 短信 MFA |
| 密码恢复 | identity | 邮件 + 固定安全问题辅助 | PARTIAL | recovery | PasswordRecovery | identity recovery | 模糊响应/哈希 | 是 | 单元/API | 3B | 客服改密 |
| RBAC 基础 | identity | USER/ADMIN_OPERATOR 人类角色、管理员 Application 用例与独立服务主体 | PARTIAL | 无新增公共 API | Principal/Role/Policy | users.roles + permission_version | 默认拒绝、管理员 MFA、即时失效、RLS | Audit/Outbox 同事务 | 单元/真实 PG | 3B | 管理员 HTTP 合同、Fact/Plan 授权、ABAC、组织 |
| Identity SQL Foundation | identity/platform | 全 Port SQL Repository、Mapper、UoW、生产装配与 readiness | DONE | Probe/既有 Identity API | Identity 全部当前对象 | identity/audit PostgreSQL | FORCE RLS、事务局部上下文、配置门禁 | 同事务 | 44 非 PG/15 PG | 3B | 管理员 HTTP 合同、完整 OAuth/MFA |
| Token 撤销与重放安全 | identity | permission_version、Session 级联撤销、Refresh Family 行锁与重放处置 | DONE | 既有 Identity API；无管理员 HTTP | Session/Grant/TokenFamily | identity/audit PostgreSQL | Redis 不作权威、重放 fail-closed | Audit/Outbox 同事务 | 12 路真实 PG 并发 | 3B | 完整限流与安全运营 |
| Audit | audit | 追加审计、持久链头与行锁 | PARTIAL | 无公共 API | AuditRecord/ChainHead | audit.events/chain_heads | 禁止敏感字段、append-only | 自身 | 单元/10 路并发真实 PG | 3B | 审计 UI |
| Outbox/后台 | audit/platform | 抢占、重试、恢复、heartbeat | PARTIAL | probes | OutboxEvent | audit.outbox | 独立事务 | 是 | 单元/PG | 3B | Agent Task Outbox |
| Redis 缓存 | platform | Token/Session 短 TTL 与降级 | PARTIAL | 间接 | CacheEntry | Redis 非权威 | Token 哈希 Key | 指标 | 单元/API | 3B | Redis Streams Agent Queue |
| 加密/密钥 | platform | 版本化 AES-GCM 与 K8s Secret Adapter | PARTIAL | 无公共 API | EncryptedValue | 密文元数据 | current/historical | 是 | 单元 | 3B | Vault/KMS |
| 邮件通知 | identity | SMTP + 开发捕获 + Outbox | PARTIAL | 间接 | Notification | audit.outbox | Secret 隔离 | 是 | 单元 | 3B | 邮件入站 |
| 导出/注销 | identity | 任务框架、7 天冷静期、撤销 | PARTIAL | export/deletion | ExportJob/DeletionRequest | identity tasks | 重认证/MFA | 是 | 单元/API | 3B | 其他模块数据删除 |
| Conversation | conversation | 正式对话业务 | SKELETON | 无 | 无 | 无 | 边界文档 | 否 | 结构检查 | 3D | 本 Slice |
| Fact/Goal/Plan/Risk/File/Secret | modules | 冻结业务模块边界 | SKELETON | 无 | 无 | 无 | 边界文档 | 否 | 结构检查 | 3D–3H | 本 Slice |
| Agent Integration | agent_integration | Platform/Agent 合同边界 | SKELETON | 无 | 无 | 无 | mTLS/JWT 设计 | 否 | 结构检查 | 3C–3D | 本 Slice |
