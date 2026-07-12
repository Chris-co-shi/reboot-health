# reboot-health Vue 3 Admin

Vue 3 Web 是 reboot-health 的正式管理与运维端，用于后续的 Task/Run 诊断、告警和审计摘要。它不代替普通用户客户端，也不承担普通用户 Plan 编辑或确认。

调用边界：

- 只调用 Health Platform 管理 API。
- 不直接调用 `health-agent`。
- 不直接访问 PostgreSQL、Redis 或 MinIO。
- 管理员不能代表用户确认 Fact、Plan 或 Risk。

当前只是 Phase 3B 的最小可构建 Admin Shell，尚未接入正式管理 API，也没有已实现的后台功能。

## 验证

```bash
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```
