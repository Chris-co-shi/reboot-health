# 0022 首发主体与 RBAC 模型

## 状态

已确认，2026-07-12 生效。

## 背景

早期 Identity 文档和代码包含健康顾问、运营、审计员和系统管理员五角色模型，与首个“训练计划→执行→反馈→调整”闭环以及最小运维权限不匹配。服务身份也不能伪装为普通用户角色。

## 决策

- 可分配给 `UserAccount` 的角色仅为 `USER` 和 `ADMIN_OPERATOR`。
- `SERVICE_HEALTH_AGENT` 是独立服务主体类型，不进入人类账号 `roles`。
- 主体类型为 `USER`、`ADMIN_OPERATOR`、`SERVICE_HEALTH_AGENT`、`BACKGROUND`、`ANONYMOUS`。
- `ADMIN_OPERATOR` 只执行确定性身份管理与故障处置；使用管理能力前强制 MFA。
- 管理员不因此获得修改健康事实、计划、风险确认、执行记录或读取完整敏感原文的权限。
- 未知角色、Scope、主体类型和跨用户访问全部 fail-closed。

## 迁移影响

旧 `HEALTH_ADVISOR/OPERATOR/AUDITOR/SYSTEM_ADMIN` 不映射为新管理员，避免静默权限提升。现有非生产数据必须显式清理或人工迁移；生产 migration 增加角色约束。

## 非目标

组织、团队、多租户、家庭授权、自定义角色、ABAC 编辑器，以及 Fact/Plan 等后续业务对象权限。
