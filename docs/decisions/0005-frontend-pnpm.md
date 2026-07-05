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

## OPEN

- OPEN: pnpm 版本是否固定为当前 `packageManager` 字段版本，还是跟随本机 Corepack 默认版本。
