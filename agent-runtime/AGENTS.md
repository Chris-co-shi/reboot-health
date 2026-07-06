# Python Health Agent Harness 规则

## 定位

`agent-runtime/` 是产品智能与任务编排核心，不是简单的模型代理。

它负责理解任务、选择 Skill、组装上下文、调用模型、选择受控 Tool、处理结果、请求确认、生成候选、记录运行轨迹和支持恢复。

Java Health Domain Kernel 仍是业务事实、安全规则、确认和领域状态权威。

## Harness 能力

长期能力包括：

- Agent Loop：有限轮次的决策和工具调用。
- Skill Registry：加载、版本化和测试领域 Skill。
- Tool Registry：声明和调用 Java 受控工具。
- Context Builder：组装最小必要上下文。
- Session Runtime：管理会话、运行、工具调用和确认。
- Memory Manager：管理事实候选、行为模式和策略经验。
- Approval Coordinator：决定自动执行、等待确认或阻断。
- Model Router：支持 Mock、云模型和未来本地模型。
- Run Trace：记录 Skill、上下文摘要、工具调用和失败分类。
- Evaluation：使用固定场景验证可靠性。
- Recovery：支持超时、取消、有限重试和恢复。

不得一次性创建所有空模块。每项能力必须由真实纵向切片驱动，并有测试和调用方。

## Agent Loop

- 必须有最大轮次、最大工具调用次数、超时和取消边界。
- 每轮产生结构化决策，不从自由文本中解析隐式工具命令。
- 工具结果可以进入下一轮，但不能无限循环。
- 缺失安全事实、权限不足或高影响操作时必须暂停并请求确认。
- 失败必须分类为模型、上下文、Schema、工具、权限、超时或系统错误。
- 只记录可审计的决策摘要和依据。

## Skill

每个 Skill 使用独立目录，至少包含：

```text
skills/<skill-name>/
├── SKILL.md
├── input.schema.json
├── output.schema.json
├── examples/
└── tests/
```

`SKILL.md` 必须说明适用场景、输入输出、可用 Tool、禁止行为、追问条件、确认条件、安全边界和完成条件。

Skill 必须小而专一，不得把 onboarding、规划、复盘和记忆全部堆进一个 Prompt。

## Tool

Python 只能通过版本化 Tool Contract 使用 Java 能力。

每个 Tool 必须声明名称、描述、输入输出 Schema、权限、影响等级、确认策略、幂等策略、超时和审计策略。

权限至少区分：

- READ
- PROPOSE
- LOW_RISK_WRITE
- CONFIRMATION_REQUIRED
- FORBIDDEN

Python 可以选择和请求 Tool；Java 最终验证权限、参数、安全规则和业务不变量。

## Context 与 Memory

- 只请求当前任务必要的数据，不加载完整数据库或全部聊天历史。
- 区分已确认事实、AI 候选、历史摘要和模型推断。
- 重要健康事实不能仅凭一次模型输出成为长期记忆。
- Memory 分为用户确认事实、行为模式候选和策略经验。
- 记忆候选必须保留来源、证据窗口、样本数、置信度和评估时间。
- 影响安全与计划的事实必须经 Java 和用户确认。

## Approval

- 查询、解释和生成草案可以自动执行。
- 降低风险或复杂度的可撤销小调整可以按策略执行。
- 新计划、增加训练负荷、重要目标变化和健康约束变化必须等待确认。
- 诊断、绕过安全规则或弱化已确认约束属于禁止行为。

## Provider 与依赖

- 兼容 Python 3.12，公共接口和数据模型使用明确类型标注。
- Provider 接口与具体模型实现分离。
- M2.5-A 只使用 MockProvider。
- 未经确认不得接入真实供应商、多 Agent 框架、向量数据库或重量工作流依赖。
- 测试不得依赖互联网或真实外部凭据。

## 可观测性与评测

每次运行至少关联 runId、trigger、selectedSkill、contextSummary、provider、promptVersion、toolCalls、policyDecisions、finalOutcome、latency、tokenUsage 和 failureCategory。

测试分层：unit、contract、scenario、eval。

## 禁止

- 不连接 PostgreSQL 或直接写业务表。
- 不直接发布 PlanVersion 或修改已确认事实。
- 不开放任意系统工具或自动安装未知 Skill。
- 不允许 Agent 自动修改自身代码。
- 不记录完整健康原文或认证信息。
- 不把 Harness 简化为一个大 Prompt 文件。

## 合同变更

Java-Python 请求、响应、错误码、Tool Contract 和 Schema 必须先形成文档或合同测试，再分别修改两端。Python 任务默认只修改 `agent-runtime/`。

## 当前阶段

M2.5-A 只实现 Model Mock 和最小 Runtime API。Agent Loop、Skills、Tools、Memory、Approval 和 Evaluation 必须在后续纵向切片中逐步落地，不得提前宣称完成。

## 验证

```bash
cd agent-runtime
python3 -m compileall agent_runtime tests
python3 -m unittest discover -s tests
```
