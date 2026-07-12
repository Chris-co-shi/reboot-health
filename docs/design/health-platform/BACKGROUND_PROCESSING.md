# 后台处理

业务事务写入 Outbox 后提交。后台线程用独立 Session 和 `FOR UPDATE SKIP LOCKED` 原子领取，先标记 PROCESSING 并提交，再在事务外执行 SMTP/安全通知/导出/删除协调，最后以独立事务标记 PUBLISHED 或退避 FAILED。

Worker 由 FastAPI lifespan 启停，禁止 daemon。它持有 stop_event、worker_id、heartbeat 和当前任务状态；异常被记录且 readiness 变为失败，启动时恢复 locked_until 已过期的 PROCESSING。SIGTERM 停止领取新任务并等待当前短任务。
