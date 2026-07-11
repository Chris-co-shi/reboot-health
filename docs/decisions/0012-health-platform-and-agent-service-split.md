# 0012 Health Platform 与 health-agent 服务拆分

## 状态

已确认，2026-07-12 生效。

替代：

- 0002 中“单体部署”的长期目标。
- 0009 的 Java/Python 多运行时职责划分。
- 0010 的 Python 模块化单体目标架构。

## 背景

现有 `health_agent/` 已证明通用 Agent Runtime、Tool Loop、Session 和恢复基础，但完整产品还需要用户身份、业务事实、Plan、文件、风险确认、管理端和生产运维。把这些职责继续放入同一 Runtime 会让模型执行状态和健康业务权威耦合。

## 决策

建立两个独立部署的 Python 服务：

- **Health Platform**：用户身份、业务权限、Conversation、Fact、Plan、Risk、File、Secret、审计和正式客户端 API 的唯一权威。
- **health-agent**：通用 Task/Run/Step、模型、Tool、Sandbox、Context、RAG、Sub-Agent、恢复和执行可观测性。

客户端只访问 Health Platform。两个服务使用内部 HTTPS、mTLS 和短期 JWT；health-agent 不直接访问 Platform 数据库，业务数据只能通过 Platform Tool API 读取或创建候选。

## 影响

正面：

- 清晰分离用户业务权威与模型执行状态。
- health-agent 可以保持通用、可测试和可横向扩展。
- 客户端、Plan 和文件安全不依赖模型 Runtime。

成本：

- 需要稳定服务合同、事件同步和分布式一致性。
- 部署、证书、回调和版本兼容更复杂。

## 约束

- 不允许创建第三个业务事实源。
- 不允许客户端直连 health-agent。
- 不允许 health-agent 直接发布 Plan 或确认 Fact。
- 现有 Phase 1–2C Runtime 必须迁移复用，不做无理由重写。
