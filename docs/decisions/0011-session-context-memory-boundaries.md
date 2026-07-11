# 0011 Session、Context、Memory 与领域事实边界

## 状态

已确认。

## 背景

当前 Runtime 已经具备 AgentSession、Message History、JSON Store、Confirmation、lease、checkpoint 和恢复协议，但默认产品入口仍是 one-shot CLI。

在真实使用中，用户会自然认为：

```text
Agent 在上一轮问了问题
→ 用户下一轮补充信息
→ Agent 应该记得此前目标和回答
```

同时，健康产品还需要保存身高、体重、健康约束、目标、计划和训练记录。若不明确区分，很容易把以下概念混在一起：

- Session Message History。
- Runtime Context。
- Conversation Summary。
- UserProfile / HealthConstraint / Goal / Plan。
- Memory Candidate。
- 已确认长期事实。

这种混淆会导致模型推断被错误写成健康事实、对话摘要变成不可追溯的长期记忆，或 Runtime 直接承担领域数据职责。

## 决策

### 1. Session Message History

Session Message History 保存某个 `session_id` 下的：

```text
system
user
assistant
assistant(tool_calls)
tool
```

作用：

- 支持连续对话。
- 支持 Tool Call 消息往返。
- 支持暂停、恢复和审计摘要。

它属于 Runtime 技术状态，不是健康领域事实。

### 2. Runtime Context

Runtime Context 只包含当前模型回合所需的运行信息，例如：

```text
currentDate
currentDateTime
timezone
locale
可用 Tool Definition
Session Message History 或其受控投影
```

Context 是每次模型调用时组装的输入，不等于持久化模型，也不自动形成长期记忆。

### 3. Conversation Summary

Conversation Summary 用于在消息历史过长时压缩旧对话。

必须保留：

- 覆盖的消息范围。
- 生成时间。
- 生成来源或模型版本。
- 是否仍保留原始消息。

Conversation Summary：

- 不是用户确认事实。
- 不得直接映射成 HealthConstraint、Goal 或 Plan。
- 不得覆盖用户原始表达。
- 可以被后续新消息纠正或重建。

### 4. 结构化领域事实

以下内容属于健康领域事实或业务状态：

```text
UserProfile
HealthConstraint
Goal
Plan / PlanVersion
TrainingRecord / DailyActionExecution
Observation / DailyRecord
```

它们必须：

- 由 Domain Service 和 Repository 管理。
- 有明确来源、版本和状态。
- 遵守确认、revision、幂等和审计规则。
- 通过只读 Tool 提供给 Agent。

Runtime 不直接创建、修改或硬编码这些事实。

### 5. Memory Candidate

Memory Candidate 是模型从对话或执行数据中提取的候选，例如：

```text
用户更偏好游泳而不是跑步
用户通常在工作日晚上训练
某种训练安排过去更容易坚持
```

Memory Candidate 必须：

- 可追溯到来源消息或记录。
- 标明候选类型和置信度。
- 可纠正、停用或替代。
- 不自动成为 UserProfile、HealthConstraint 或 Goal。
- 重要健康事实必须经过用户确认。

### 6. Clarification 不属于 PendingAction

普通澄清问题，例如：

```text
你的年龄是多少？
每周可以训练几天？
目前有哪些器械？
```

通过同一 Session 的下一轮 user message 继续，不创建 PendingAction，不进入 WAITING_CONFIRMATION。

PendingAction 只用于高影响 Tool、写入或发布审批。

### 7. 写入与确认边界

交互语义分为：

```text
Clarification：补充信息
Proposal：未执行候选
Confirmation：用户批准写入或发布
```

模型可以生成 Proposal，但确定性代码负责：

- 校验。
- Safety Guard。
- 内容哈希与 revision。
- Confirmation。
- 幂等写入。
- 审计。

## 分层关系

```text
AgentSession
└── Message History
    └── 可选 Conversation Summary

Runtime Context
├── Runtime Environment
├── Session History / Summary
└── Read-only Tool Definitions

Domain Facts
├── UserProfile
├── HealthConstraint
├── Goal
├── Plan / PlanVersion
├── Execution Records
└── Observations

Memory Candidate
└── 经确认后映射到既有领域事实或偏好模型
```

## 生命周期

### Session

- 可以创建、继续、暂停、恢复和结束。
- Session 删除策略属于技术数据生命周期。
- Session 结束不等于删除健康领域事实。

### Domain Facts

- 生命周期由业务状态和审计规则决定。
- 不能因为 Session 被删除而删除。
- 不能因为 Conversation Summary 改写而改变。

### Memory Candidate

- 默认是候选。
- 可以确认、拒绝、纠正、失效或被替代。
- 不允许静默写入。

## 隐私与日志

- 普通日志不得记录完整 Message History、健康原文或 Conversation Summary。
- JSON Runtime Store 是本地明文，仅适合受控开发环境。
- 正式产品必须定义数据保留、删除、备份和静态加密策略。
- Trace 只记录运行摘要，不记录长期 Memory 内容。

## 影响

### 正面影响

- 连续对话可以先于健康数据库独立落地。
- 健康事实不会被模型自由记忆替代。
- Conversation Summary 可以安全演进而不污染领域模型。
- Confirmation 只处理真正需要批准的操作。
- 后续可以分别评测会话质量、工具读取质量和 Memory 提取质量。

### 成本

- 需要分别维护 Session Store 与健康领域 Repository。
- 长对话压缩需要独立设计和测试。
- Memory Candidate 需要来源、状态和确认模型。

## 非目标

本 ADR 不决定：

- Conversation Summary 的具体算法和阈值。
- 健康领域数据库选型。
- Memory Candidate 的最终 Schema。
- 向量数据库。
- 多 Agent 共享记忆。

## 后续实施

- Phase 2C：Interactive Session 与 Conversation Context。
- Phase 3A：结构化健康领域 Read Model 与只读工具。
- Phase 4：经确认写入领域事实。
- Phase 5 或后续：Memory Candidate 提取、确认和纠正。
