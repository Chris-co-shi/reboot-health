# 数据模型

Schema：`identity` 保存 user、profile、role、grant、session、token、verification、recovery、MFA、OAuth client/code、export/deletion；`audit` 保存追加审计与 Outbox。

Domain、API DTO、SQLAlchemy Model 三者分离。所有时间为 UTC，资源 ID 使用 UUID v7 兼容生成器。高并发表具有唯一约束、版本或行锁。用户私有表启用 RLS，事务以 `SET LOCAL app.user_id/app.actor_kind` 设置上下文。

Alembic 仅一个 Head；初始迁移创建 Schema、表、索引、约束、RLS/策略和审计禁止更新/删除触发器。跨模块数据库外键默认禁止。
