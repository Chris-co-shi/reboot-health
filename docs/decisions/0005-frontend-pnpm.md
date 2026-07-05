# 0005 前端使用 pnpm

## 状态

已确认

## 决策

前端包管理使用 pnpm。

## 原因

用户已明确要求使用 pnpm 管理前端依赖。

## 影响

- 前端使用 `pnpm-lock.yaml` 锁定依赖。
- README 和 AGENTS 中的前端命令使用 pnpm。
- Dockerfile 使用 Corepack 启用 pnpm。
- pnpm 版本以 `frontend/package.json` 的 `packageManager` 字段为准。
