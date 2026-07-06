# 架构方案

## 核心定位

`reboot-health` 采用三层核心结构：

```text
Python Health Agent Harness
    产品智能与任务编排核心

Java Health Domain Kernel
    已确认事实、安全规则和领域状态权威

Flutter Client
    正式用户交互与多平台体验
```

Python 决定下一步应该做什么；Java 决定什么允许做并可靠保存；Flutter 负责用户如何表达、确认和行动。

Python 是智能控制流核心，但不是业务事实权威。Java 是可信领域内核，但不是 Agent 编排核心。

## 系统组件

```text
Flutter Client
    ↓ REST / SSE
Java Edge + Health Domain Kernel
    ├── PostgreSQL 17
    ├── Agent Tool API
    └── internal HTTP → Python Health Agent Harness

Vue Debug Tool ── REST → Java Backend
```

- Python：理解任务、选择 Skill、组装上下文、调用模型、请求 Tool、处理结果和生成候选。
- Java：保存事实、执行规则、管理确认、设备身份、审计、幂等和 AgentRun 状态。
- Flutter：唯一正式用户客户端。
- Vue：冻结的内部调试工具。

## Python Health Agent Harness

长期能力包括：

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

约束：

- 不访问 PostgreSQL。
- 不直接写 Goal、HealthConstraint、Plan 或 PlanVersion。
- 不直接发布计划或改变确认状态。
- 不绕过 Java 权限、安全规则和领域不变量。
- 不把全部能力堆进一个系统 Prompt。

M2.5-A 仅提供稳定 Model Mock 和最小 Runtime API，完整 Harness 尚未实现。

## Java Health Domain Kernel

采用 Java 21、Spring Boot、模块化单体、Flyway、MyBatis-Plus 和 Testcontainers。

```text
Controller -> Application Service -> Domain -> Repository Port
Persistence Adapter -> Repository Port
External Adapter -> Application Port
```

主要模块：

- `profile`：用户档案和已确认健康约束。
- `goal`：目标唯一事实来源。
- `plan`：长期 Plan 和 7 天 PlanVersion 发布引擎。
- `agent`：AgentRun 状态、Runtime 调用边界和结果校验。
- `device`：设备初始化、配对、认证和撤销。
- `audit`：追加写业务与安全审计。
- `idempotency`：关键写请求的幂等边界。

职责：

- 保存已确认事实。
- 提供面向业务意图的 Agent Tool。
- 校验 Tool 权限、影响等级、确认策略和幂等边界。
- 执行确定性规则和领域不变量。
- 保存 AgentRun、ToolCall、确认和业务审计结果。

约束：

- 领域层不依赖 Web、Mapper、Python 或 Flutter。
- 数据库事务中不调用 Python 或其他远程服务。
- Java 不负责 Skill 选择、Prompt 内容和模型控制流。
- 已确认计划继续由现有 PlanVersion 引擎发布。

## Agent Tool Contract

Java CRUD API 不直接等同于 Agent Tool。Tool 应面向业务意图，并声明：

- 名称和用途。
- 输入输出 Schema。
- 权限和影响等级。
- 确认策略。
- 幂等、超时和审计策略。

Python 选择并请求 Tool；Java 最终决定是否允许执行。

## Agent 运行模型

区分：

- Conversation：长期对话。
- Session：连续交互上下文。
- AgentRun：一次明确任务。
- ToolCall：一次受控工具调用。
- Confirmation：等待用户授权的状态。

目标调用链：

```text
Flutter 发起目标
→ Java 认证并创建 AgentRun
→ Python 选择 Skill 并构建上下文
→ Python 请求 Java Tool
→ Java 校验并返回结果
→ Python 继续有限轮次决策
→ 输出候选或等待确认
→ Java 保存权威状态
→ Flutter 展示卡片和确认入口
```

M2.5-A 当前仍是一次 Mock Runtime 执行，不代表完整 Agent Loop 已完成。

## Memory 与 Approval

Java 保存已确认事实、目标、健康约束、计划、执行事实和影响安全判断的信息。

Python 管理会话摘要、非事实任务状态、行为模式候选、策略经验候选和上下文压缩结果。

影响安全和计划的记忆候选必须经过 Java 保存边界和用户确认。

查询、解释和草案生成可以自动执行；降低风险或复杂度的小调整可以按策略执行；新计划、增加训练负荷、重要目标和健康约束变化必须等待确认。

## 可观测性与评测

每次 Agent Episode 应关联 runId、trigger、selectedSkill、contextSummary、provider、promptVersion、toolCalls、policyDecisions、finalOutcome、latency、tokenUsage 和 failureCategory。

评测覆盖正确性、安全性、Tool 选择、确认判断、成本和失败恢复。

## Flutter 客户端

目标平台：iOS、Android、macOS、Windows。

- 移动端优先，桌面端做适配布局。
- 只调用 Java 对外 API。
- 自然语言负责表达和解释，卡片负责行动和确认。
- 不向普通用户展示 UUID、revision、PlanVersion 或内部枚举。

M2.5-A 的真实 runner 和四端构建仍有环境阻塞。

## Vue 调试工具

Vue 只用于已有数据检查和阻塞性修复，不新增正式业务页面，不与 Flutter 双重实现新功能。

## 设备认证边界

第一阶段使用私有设备认证，不建设完整 IAM。首台设备通过一次性初始化码建立，后续设备通过授权设备配对。每台设备独立、可撤销，主设备转移必须显式执行。

精确 API、数据库表和错误码见 `api-db.md`；安全不变量见 `safety-rules.md`。

## 文档边界

- 产品体验和范围：`product-scope.md`
- 业务模型：`domain-model.md`
- 技术合同：`api-db.md`
- 安全规则：`safety-rules.md`
- 当前状态：`mvp-exec-plan.md`
- 重大决策：`decisions/`
