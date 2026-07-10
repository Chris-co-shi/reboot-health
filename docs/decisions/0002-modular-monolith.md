# 0002 模块化单体架构

## 状态

已扩展。

模块化单体原则继续有效；当前 Python-first 运行时、通用 Agent Loop 和 legacy 迁移边界由 [`0010 Python 模块化单体与通用 Agent Loop`](0010-python-modular-monolith-and-agent-loop.md) 扩展。

## 背景

项目是单人使用的健康管理和训练辅助应用，目标是尽快打通计划、执行、分析、AI 建议、用户确认和计划版本生成的闭环，同时保持部署和维护简单。

本文最初基于 Java 后端模块划分作出决策。当前实现已迁移为 Python-first，但“不拆微服务、保持清晰模块边界”的核心决策不变。

## 决策

MVP 采用模块化单体，不拆微服务。

历史模块语义包括：

- `profile`
- `goal`
- `plan`
- `execution`
- `metrics`
- `analysis`
- `rules`
- `ai`
- `adjustment`
- `audit`

这些语义后续应迁移为 Python 模块、Domain Service 与 Repository Port，而不是继续扩展旧 Java 运行时。

## 备选方案

- 微服务：边界更强，但对个人项目过度复杂，会增加网络、部署、观测和一致性成本。
- 单包 CRUD：初期文件少，但计划版本、规则和 AI 调整边界容易混杂。
- 模块化单体：保持部署简单，同时能表达 Runtime、Tool、Domain 和 Persistence 边界。

## 影响

- 一个主要 Python 应用。
- 一个本地持久化边界，具体技术在后续阶段确认。
- 领域聚合或 Domain Service 负责关键状态转换。
- 模块依赖方向需要持续维护。
- 不引入微服务、消息队列或 Kubernetes 作为当前架构前提。

## OPEN

- OPEN：是否增加 Python 模块依赖检查脚本。
- OPEN：本地持久化最终使用 SQLite 还是其它方案。
