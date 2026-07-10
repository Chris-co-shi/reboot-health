# 0009 Python Health Agent Harness 与可信领域内核

## 状态

已替代。

由 [`0010 Python 模块化单体与通用 Agent Loop`](0010-python-modular-monolith-and-agent-loop.md) 替代。

本文保留为历史决策，描述 Java、Python、Flutter 多运行时阶段的职责划分；不得再作为当前实现依据。

## 背景

项目进入 Java、Python、Flutter 和 Vue 多运行时阶段，需要明确智能控制流、事实安全和用户体验的职责边界。

## 决策

### 核心架构

- Python Health Agent Harness 是产品智能与任务编排核心。
- Java Health Domain Kernel 是已确认事实、安全规则、权限、确认、审计、幂等和领域状态权威。
- Flutter 是正式用户客户端。
- Vue 冻结为内部调试工具。

核心关系：

> Python 决定下一步应该做什么；Java 决定什么允许做并可靠保存；Flutter 负责用户如何表达、确认和行动。

Python 是智能控制流核心，但不是业务事实权威。Java 是可信领域内核，但不是 Agent 编排核心。

### Harness Engineering

Python Harness 后续按纵向切片建设：

- Agent Loop
- Skill Registry
- Tool Registry
- Context Builder
- Session Runtime
- Memory Manager
- Approval Coordinator
- Model Router
- Run Trace
- Evaluation
- Recovery

不一次性创建全部空框架，不把 Harness 简化为一个大 Prompt。

### 运行时职责

Python 负责选择 Skill、组装上下文、调用模型、请求 Java Tool、处理结果、生成候选和记录运行摘要。

Java 负责保存事实、提供受控 Tool、校验权限和确认策略、执行确定性规则以及保存 AgentRun 和审计结果。

Flutter 负责自然语言与页面卡片交互，只调用 Java 对外 API。

### 交付方式

- M2.5-A：技术骨架。
- M2.5-B：首次 AI 规划闭环。
- M2.5-C：最小今日行动和执行反馈。
- 每个实施任务只能有一个主模块。
- 跨运行时改动先定义 Tool Contract 或 Schema，再分别实施，最后单独集成验证。

## 影响

- Goal 继续作为目标唯一事实来源。
- HealthConstraint 通过候选与用户确认演进。
- 周计划继续由现有 PlanVersion 引擎发布。
- Python 不访问业务数据库，不直接发布计划。
- Java 不负责 Skill 选择、Prompt 编排和智能控制流。
- 新业务不在 Vue 和 Flutter 中双重实现。
- README 和根 AGENTS.md 将 Harness Engineering 作为项目核心定位。

## 非目标

- 不建设复杂多 Agent 自治。
- 不在当前阶段引入消息队列、向量数据库或重量工作流平台。
- 不建设公开多用户产品和运营后台。
