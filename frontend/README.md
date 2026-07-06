<div align="center">

# Vue Debug Tool

### Frozen internal interface for existing M2A / M2B data

<p>
  <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3-42B883?logo=vuedotjs&logoColor=white">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-Strict-3178C6?logo=typescript&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/Status-Frozen-636E72">
</p>

**这不是正式产品客户端。正式体验由 Flutter Client 承担。**

</div>

## Allowed work

- 修复阻塞既有数据查看或人工验收的问题。
- 适配已确认的后端接口变化。
- 修复类型、构建和明显展示错误。
- 提供最小内部排障信息。

## Out of scope

- 不新增 Agent、Program、Phase、DailyAction 或 Observation 正式页面。
- 不与 Flutter 双重实现新产品能力。
- 不把 Vue 恢复为管理后台或主客户端。
- 不绕过后端认证、幂等、审计或领域状态机。

## Verify

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

> Vue 构建通过不代表 Flutter 正式客户端已经验收。

详细规则见 [`AGENTS.md`](AGENTS.md)，产品架构见 [`../docs/architecture.md`](../docs/architecture.md)。
