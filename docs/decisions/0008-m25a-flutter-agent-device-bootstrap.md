# 0008 M2.5-A Flutter、Agent Runtime 与设备 Bootstrap

## 状态

已确认。

## 背景

M2A 和 M2B 已完成核心计划数据能力。M2.5-A 需要先建立正式主客户端、AgentRun 技术链路和私有设备认证边界，为后续 AI 首次规划闭环和今日执行反馈提供基础设施。

## 决策

- Flutter 是唯一正式主客户端，目标平台为 iOS、Android、macOS、Windows。
- Vue 冻结为内部调试工具，不新增正式业务页面。
- Java 是业务事实、AgentRun、确认、安全和状态的唯一权威系统。
- Python Agent Runtime 只负责模型调用/编排和结构化输出；M2.5-A 默认 Model Mock。
- Python 不连接 PostgreSQL，不直接写业务表，不直接发布计划。
- 第一阶段单用户，但新增模型保留 `userId` 与 `deviceId` 边界。
- 第一阶段不引入消息队列、Redis、向量数据库、多 Agent 框架或复杂工作流平台。
- 首台设备初始化必须由服务端 CLI 生成短时一次性 bootstrap code。
- 服务端只保存 bootstrap code 和 refresh credential 的安全摘要，不保存明文。
- 后续设备只能由已授权设备创建 `PairingSession` 后配对。
- 每台设备拥有独立 deviceId 和独立凭据，可单独撤销。
- 二维码或配对 payload 不得携带长期 access token 或 refresh credential。

## 影响

- 新增 `agent-runtime/`。
- 新增 `clients/flutter/`。
- 后端新增 `agent` 与 `device` 模块。
- 新增 V6 Flyway 迁移，创建 AgentRun、AgentToolCall、Device、PairingSession、DeviceCredential 等表。
- 不改变现有 Profile、Goal、HealthConstraint、Plan、PlanVersion 的业务语义。

## 非目标

- 不接入真实云模型。
- 不实现自然语言访谈、Goal 开放模型、HealthConstraint 候选、Program、Phase 或 WeeklyPlan 生成。
- 不实现 DailyAction、DailyActionExecution 或 Observation。
- 不建设完整 IAM、注册、密码找回、角色权限或多租户。
