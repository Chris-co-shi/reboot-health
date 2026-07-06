# 业务领域模型

本文档只描述业务聚合、语义和不变量。设备认证、AgentRun、加密信封等技术运行模型的字段和表结构见 `api-db.md`。

## 建模原则

- AI 输出是候选，不是领域事实。
- 用户确认、计划发布、执行记录和分析结果必须分离。
- 历史事实不能随计划或 AI 理解变化而改变。
- 用户原始表达不得被内部标签覆盖。
- 医疗相关内容只表达限制、来源、提醒和安全边界，不生成诊断结论。
- 目标、约束和计划各自只有一个事实来源。

## UserProfile

用户基础档案，为计划日期、展示和上下文提供稳定基础信息。

核心语义：

- 第一阶段只有一个当前用户档案。
- `baselineWeightKg` 只表示建档基线，不代表当前体重。
- 当前体重以后从最新 Observation 或指标记录获得。
- 时间相关业务必须使用档案时区或显式默认时区，不使用服务器默认时区。
- 档案不承载训练计划、每日状态或模型推断。

## HealthConstraint

已确认的健康约束，表达用户陈述、专业建议来源、身体区域、限制和注意事项。

当前状态：

- M2A 已实现手工创建、修改、状态变化和归档。
- 归档不物理删除。
- 归档后禁止普通编辑和状态变化。
- 当前有效约束进入计划检查和 Agent 上下文。

AI-first 演进规则：

- AI 只能生成 `HealthConstraintCandidate`，不能直接修改已确认约束。
- 候选必须保留用户原始陈述、风险描述、建议限制、来源和不确定性。
- 重要约束经用户确认后，才映射到同一个 HealthConstraint 事实模型。
- 固定类型和身体区域仅作为可选归一化标签，不限制自然语言表达。
- AI 不得自动删除、停用或弱化已确认约束。

## Goal

Goal 是用户目标的唯一事实来源，为计划、进度解释和 AI 上下文提供稳定身份。

当前状态：

- M2A 已实现固定类型、结构化指标、优先级、状态和归档。
- 目标不是计划任务，不直接包含每日动作。
- `ACTIVE`、`PAUSED` 可以继续编辑；终态目标不恢复为进行中。

开放目标演进规则：

- 不新增并行 `OpenGoal` 表或第二套目标事实来源。
- `originalText` 和 `desiredOutcome` 将成为开放表达核心。
- GoalType 只作为可选归一化标签。
- targetValue、unit、baselineValue、targetDate 等结构化指标可以为空。
- 成功标准、指标、标签、假设和待澄清问题作为同一 Goal 的扩展信息。
- 旧 Goal 保留原字段，不通过迁移伪造用户原始表达或期望结果。
- AI 只能提出创建或补全候选，用户确认后才写入事实。

## Plan

Plan 是长期计划身份。第一阶段只维护一个当前 Plan，周期内容由 PlanVersion 表达。

Plan 不等于长期 Program：

- Plan 是现有持久化身份和版本容器。
- Program 是后续 AI-first 的用户可读长期方向。
- Program 不应取代或复制 PlanVersion 的发布职责。

## PlanVersion

PlanVersion 是 7 天计划周期版本，也是当前周计划的唯一发布引擎。

状态：

- `DRAFT`：可编辑、可取消、可确认。
- `CONFIRMED`：已确认且不可修改。
- `SUPERSEDED`：同周期旧确认版本被新修订替代。
- `CANCELLED`：已取消草案。

不变量：

- 周期固定 7 天。
- 当前计划通过用户时区和日期查询，不使用 `ACTIVE` 状态。
- 同周期只能有一个当前草案和一个当前确认版本。
- 不同确认周期不得重叠。
- 同周期修订确认后显式替代旧确认版本。
- 确认时保存健康约束和目标稳定快照。
- 已确认、已替代和已取消版本不可原地修改。
- 编辑、确认和取消必须校验 revision。
- AI 只能生成草案候选，用户确认后由 Java 计划领域服务发布。

## PlanDay 与 PlanItem

PlanDay 表示版本周期内的一天；可确认草案必须恰好包含连续 7 天。

PlanItem 是计划日的人工计划条目：

- 不建立复杂动作库。
- 数值字段不得为负数。
- RPE 等评分必须满足明确范围。
- 可以关联同一个 Goal 事实来源。
- 休息日允许没有条目。
- 用户界面以后通过 DailyAction 展示，不直接暴露内部版本和条目技术结构。

## 后续 AI-first 模型

以下模型已经确认方向，但尚未在 M2.5-A 实现。

### Program

用户可读的 8 到 24 周长期方向，回答总体目标、策略、阶段、安全边界和成功标准。

Program 是规划语义，不直接发布每日计划，也不建立并行周计划事实源。

### Phase

Program 下 2 到 6 周的当前阶段，表达阶段重点、进入条件、退出条件和成功标准。

### Weekly Plan

用户语言中的周计划。内部必须映射到现有 PlanVersion、PlanDay 和 PlanItem，不新建独立发布引擎。

### DailyAction

用户当天看到的行动卡，来源于已确认周计划、当天状态和允许的低风险调整。

DailyAction 不是 PlanItem 表单的简单改名；它需要包含用户可读原因、完成定义和可调整范围。

### DailyActionExecution

回答“计划做了没有、做了多少”的执行事实。

最小状态方向：完成、部分完成、跳过。执行事实不得整体塞入 Observation。

### Observation

回答“在某个时间观察到了什么”，用于体重、睡眠、步数、心率、疲劳、疼痛和设备数据等观察事实。

Observation 与执行记录相互关联，但不能互相替代。

### Memory Candidate

Agent 从用户表达或执行数据中提取的记忆候选。分为：

- 用户确认事实。
- 行为模式候选。
- 策略经验。

重要健康事实不能仅凭一次模型推断成为长期记忆。候选必须可追溯、可纠正、可停用或替代。

## 模型关系

```text
UserProfile
├── HealthConstraint
├── Goal
└── Program（计划中）
    └── Phase（计划中）

Plan
└── PlanVersion
    ├── PlanDay
    │   └── PlanItem
    └── Goal Snapshot / HealthConstraint Snapshot

PlanVersion
→ DailyAction（计划中）
→ DailyActionExecution（计划中）

执行反馈与设备数据
→ Observation（计划中）
→ Memory Candidate（计划中）
```

## 当前未决事项

- `OPEN`：开放 Goal 扩展字段的最终最小集合。
- `OPEN`：Program 与现有 Plan 的持久化关系采用独立聚合还是适配读模型。
- `OPEN`：DailyAction 是持久化命令模型还是由周计划投影产生。
- `NEEDS_MEDICAL_REVIEW`：健康约束和自动调整的具体医学阈值。

未决事项不得在实现中自行定案。