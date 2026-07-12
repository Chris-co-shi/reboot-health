# audit 模块

状态：`PARTIAL`（Slice 2 实现中）。

职责：追加审计哈希链、Outbox 状态、SKIP LOCKED 多 Pod 抢占与过期恢复。

主要位置：

```text
modules/audit/
├── domain/            AuditEvent、OutboxEvent、OutboxStatus
└── adapters/          AuditEventRow / OutboxEventRow / SqlAuditRepository / SqlOutboxRepository
```

当前 Slice 已完成：

- Alembic 唯一主线、SQLAlchemy 2、PostgreSQL Outbox `FOR UPDATE SKIP LOCKED` 抢占。
- 同事务追加审计，避免业务提交后再补审计造成的漏洞。
- 新增 `audit.chain_heads` metadata、行锁更新 Repository 与 0002 migration；10 路并发真实 PostgreSQL 17 测试验证单链无分叉。
- Audit、Outbox、Identity 状态和 after-commit hook 的提交/回滚边界已有真实 PostgreSQL 验证。

未完成：SMTP Outbox Processor、OTel instrumentation；审计管理 UI 不属于本 Slice。
