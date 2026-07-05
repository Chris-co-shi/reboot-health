# 0007 计划版本状态和 POST 幂等

## 状态

已确认。

## 决策

- M2B 不使用 `ACTIVE` 计划版本状态。
- 当前计划通过 `CONFIRMED` 版本日期范围计算。
- 同周期新版本确认时，旧 `CONFIRMED` 版本变为 `SUPERSEDED`。
- 不同周期的历史、当前和未来 `CONFIRMED` 版本可以共存，但不能重叠。
- 创建资源和关键状态变化的 POST 必须要求 `Idempotency-Key`。
- 幂等记录、业务修改和审计写入必须在同一事务内完成。
- 不使用 Redis 锁、分布式锁或消息队列。

## 原因

计划是否当前有效是日期事实，不应由定时任务或全局唯一 `ACTIVE` 状态维护。HTTP 幂等必须独立于数据库一致性约束，避免网络重试或双击导致重复创建、重复确认或重复审计。

## 影响

- 新增 `plan_version` exclusion constraint 防止重叠确认周期。
- 新增 `idempotency_record` 表长期保存幂等记录。
- 前端 service 层统一传递 `Idempotency-Key`，页面通过 composable 管理同一次用户操作的 key 生命周期。
