# Vue 3 Admin 规则

`frontend/` 是 reboot-health 的正式管理与运维端。

- 只调用 Health Platform 管理 API。
- 不直接调用 `health-agent`、PostgreSQL、Redis 或 MinIO。
- 不承担普通用户 Plan 编辑或用户确认。
- 管理员不能修改用户 Fact/Plan 内容、代表用户确认风险，或伪造任务成功。
- 使用 Vue 3、TypeScript strict 和现有 pnpm 工程约定。
- 当前只保留 Admin Shell；没有批准的管理端 Slice 时不得固化正式 API 或实现后台业务。
- 不在日志或控制台输出健康数据、Token、Secret 或完整 Tool 结果。

验证：

```bash
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```
