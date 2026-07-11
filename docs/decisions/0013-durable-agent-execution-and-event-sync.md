# 0013 持久异步执行、调度与事件同步

## 状态

已确认，2026-07-12 生效。

替代 0006 中“Redis 暂不进入 MVP”的长期结论；该结论只作为旧阶段历史保留。

## 背景

生产体验要求页面断开后任务继续、Worker 崩溃后恢复、多实例并发受控，并让 Health Platform 获得近实时执行状态。同步请求或仅靠本地 JSON 文件不能满足这些要求。

## 决策

- Task 是连续用户目标，Run 是一次执行尝试，Step 是可检查执行单元。
- health-agent 分为 API 和 Worker 两种进程角色。
- PostgreSQL 保存 Task、Run、Step、Checkpoint、ToolCall、PendingAction 和 Outbox，是权威存储。
- Redis Streams 只提供调度和协调加速，不是业务权威。
- lease、heartbeat 和 fence generation 防止旧 owner 继续写入。
- Platform/Agent 状态同步使用 Transactional Outbox、HTTP callback、Inbox 幂等、sequence gap 检测、pull/snapshot 和周期 reconciliation。
- 交付语义是 at-least-once + 幂等 + 对账，不声称 exactly-once。

## 影响

正面：

- 断网和页面关闭不影响后台 Task。
- Redis 丢失或重复消息可由 PostgreSQL 重建。
- 事件回调失败不会静默丢失。

成本：

- 需要 Reconciler、dead-letter、事件回放和状态投影。
- Tool 和外部副作用必须明确幂等、补偿和未知结果处理。

## 约束

- `MODEL_CALL_IN_FLIGHT`、`TOOL_CALL_IN_FLIGHT` 和 `FINALIZING` 默认 fail-closed。
- 只有可证明幂等或结果可查询的操作允许自动重放。
- Redis 状态不得覆盖 PostgreSQL 权威。
- RabbitMQ 不是第一版依赖，但 Queue/Publisher Port 必须允许未来替换。
