# 可观测性

OpenTelemetry 提供 traces/metrics；结构化 JSON 日志包含 timestamp、level、service、environment、version、trace_id、request_id、user_id_hash、module、use_case、event、duration_ms、error_code。

指标覆盖 HTTP、数据库、Redis、认证、授权、Outbox、后台 heartbeat、邮件与预留 health-agent 调用。日志过滤器对 Token、密码、MFA、Secret、邮箱/手机号和健康原文进行拒绝或哈希化。

`/health/live` 只检查进程；`/health/startup` 检查配置；`/health/ready` 检查 PostgreSQL、迁移版本与后台 heartbeat。Redis/SMTP/MinIO 默认降级而非拖垮全部 Pod。
