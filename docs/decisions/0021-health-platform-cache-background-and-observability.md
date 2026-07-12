# 0021 Health Platform 缓存、后台处理与可观测性

## 状态

已确认，2026-07-12 生效。

## Context

多 Pod 部署需要共享认证缓存、可靠通知与可观察的轻量后台工作，但本阶段不引入额外 Worker 系统。

## Decision

PostgreSQL 始终为权威；Redis 仅作短 TTL 认证缓存和限流，故障时回查 PostgreSQL且绝不绕过认证。每个 Pod 运行一个 lifespan 管理的非 daemon 后台线程，以 `stop_event`、heartbeat、优雅退出和 PostgreSQL `FOR UPDATE SKIP LOCKED` 抢占处理 Outbox。OpenTelemetry、结构化脱敏日志、指标与 live/ready/startup Probe 形成运行基线。

## Alternatives

- Redis 作为会话权威：丢失时会破坏认证正确性。
- daemon 线程：可能静默死亡或在退出时丢任务。
- Celery/RabbitMQ：超出当前部署边界。

## Consequences

需要 readiness 感知线程死亡、过期 PROCESSING 恢复、退避/最大重试、SMTP 与开发捕获适配器。

## Security impact

Redis Key 仅使用 Token 哈希且 TTL 不超 Token；日志不记录凭据；后台处理不继承请求 Secret 或 RLS 上下文。

## Migration impact

未来可将 Outbox 消费迁移到独立 Worker，但事件 ID、状态和幂等合同保持不变。

## Superseded relationship

扩展 ADR 0013 的 Outbox/Redis 原则和 ADR 0017 的 Kubernetes 多副本运行边界。

## Validation

缓存降级、Outbox 多 Worker 抢占/恢复、线程生命周期、Probe 与日志脱敏测试。
