# 产品范围

## 产品定位

`reboot-health` 是面向单个用户的 AI-first 健康、减脂和规律训练辅助系统。

产品核心不是让用户维护复杂后台，而是让 Agent 通过自然语言理解目标、限制和执行反馈，在确定性工具、安全边界、确认和审计约束下提供可解释的行动建议与计划提案。

本项目不做医学诊断，不替代医生意见。

## 当前工程定位

当前与目标运行形态是 Python-first 模块化单体：

```text
用户入口
→ Agent Runtime
→ OpenAI-compatible LLM
→ 受控 Tool Runtime
→ Domain Service
→ Repository Port
→ Persistence Adapter
```

项目工程价值不只是调用模型，而是建设：

- 通用有限轮次 Agent Loop。
- 连续、可恢复的 Session。
- 可声明、可校验、可审计的 Tool Contract。
- 最小必要 Context。
- 结构化健康领域事实。
- 确定性 Safety Guard。
- Proposal、Confirmation 与受控写入。
- Trace、Evaluation 和 Recovery。

历史 Java、Flutter、Vue 和 Compose 代码仍在仓库中，但属于 legacy，不是当前产品入口。

## 当前用户体验

当前开发入口是 one-shot CLI：

```bash
python3 -m agent.main --user-text "..."
python3 scripts/agent_console.py --user-text "..."
```

一次命令只接收一次用户输入。模型和工具可以在单次 Agent Run 内多回合，但不同进程之间没有对话连续性。

Phase 2C 的目标是新增交互式 CLI，让用户启动一次程序后可以连续回答 Agent 的追问，并可显式恢复同一 Session。

## 核心原则

- 用户主要通过自然语言表达现状、目标、偏好和不适。
- Agent 可以直接回答，也可以按需调用受控工具；不要求每个请求进入固定流程。
- 模型输出默认是解释、候选或草案，不自动变成已确认事实。
- 确定性安全规则优先于模型输出。
- 重要健康事实、目标变化、计划发布和训练负荷增加必须进入确认边界。
- Tool 只能执行声明过的能力，不开放 shell、任意文件系统或任意 SQL。
- 产品默认采用单 Agent；只有未来出现明确上下文隔离或专门权限需求时才评估 Sub-Agent。
- 项目保持模块化单体，不引入微服务、消息队列或重量级工作流平台。

## 第一条产品闭环

长期目标闭环：

```text
自然语言描述
→ Agent 按需读取已确认档案与近期执行数据
→ 必要时提出关键澄清问题
→ 生成计划或调整 Proposal
→ 确定性 Safety Guard
→ 用户确认
→ 发布新的计划版本或写入记录
→ 今日执行反馈
→ 周期复盘与下一次调整
```

这不是固定工作流。Agent 仍可根据任务直接回答、读取工具或提出澄清问题；确定性代码只负责安全、状态转换和业务不变量。

## 实施路线

当前状态以 [`mvp-exec-plan.md`](mvp-exec-plan.md) 为准。

```text
Phase 1：真实 Provider、配置与 legacy 兼容链路
Phase 2A：通用只读 Tool Call Agent Loop
Phase 2B：Runtime 状态、确认、恢复与持久化安全基础
Phase 2C：Interactive Session & Conversation Context
Phase 3A：健康领域 Read Model、Repository Port 与只读工具
Phase 3B：确定性健康 Safety Guard
Phase 4：Proposal、Confirmation 与受控写入
Phase 5：执行记录与动态调整闭环
Phase 6：产品 API 与客户端集成
Phase 7：生产化、安全、评测与运维
Phase 8：高级 Agent 能力（可选）
```

当前下一阶段是 Phase 2C，不直接跳到健康领域工具或复杂 Memory。

## 交互语义

必须区分三类用户交互：

| 类型 | 示例 | Runtime 含义 |
|---|---|---|
| Clarification | “请告诉我年龄和当前体重” | 普通下一轮用户输入，不创建 PendingAction |
| Proposal | “建议将每周训练从 5 天改为 3 天” | 尚未执行的候选 |
| Confirmation | “确认发布这个计划版本吗？” | 高影响写入或发布的批准边界 |

“Agent 停下来问我需要什么信息”首先依赖连续 Session，不依赖 Confirmation 状态机。

## Session、Context、Memory 与领域事实

详细决策见 [`decisions/0011-session-context-memory-boundaries.md`](decisions/0011-session-context-memory-boundaries.md)。

规则：

- Session Message History 用于连续对话。
- Conversation Summary 只用于控制上下文长度。
- UserProfile、HealthConstraint、Goal、Plan 和执行记录是结构化领域事实。
- Memory Candidate 是模型推断候选，确认前不得生效。
- 模型不能把一次聊天内容自动写入长期用户画像。

## 自然语言与结构化界面

未来正式体验倾向“自然语言 + 结构化卡片”：

- 自然语言用于描述目标、补充状态、回答追问和理解原因。
- 结构化卡片用于健康事实候选、计划 Proposal、确认、执行反馈和趋势。

正式客户端选型尚未确认。客户端只能通过正式产品 API 使用能力，不直接访问数据库或内部 Tool handler。

## 自动化与确认

无需确认：

- 普通知识解释。
- 只读查询。
- 纯计算 Tool。
- 普通澄清问题。
- 生成未发布的草案或 Proposal。

通常需要确认：

- 将模型推断写为用户健康事实。
- 增加训练负荷或风险。
- 修改重要目标或健康限制。
- 发布新计划版本。
- 执行不可逆或高影响写操作。

Confirmation 是 Runtime 暂停恢复协议，不设计成普通模型 Tool。

## 数据输入原则

- 优先读取已确认事实、执行记录和设备/系统已有数据。
- 模型不能把推断自动写成事实。
- 信息不足时优先询问当前任务最关键的问题。
- Runtime 不硬编码用户健康信息。
- 健康领域数据通过 Domain Service 和 Repository Port 提供。
- 普通日志不保存完整健康原文、完整 Prompt 或 raw model response。

## 当前不做

- 医学诊断、处方或替代医生建议。
- 未经确认发布计划或增加训练风险。
- 公开多用户平台、运营后台、社区、排行榜、商城和支付。
- 默认多 Agent 或复杂 Sub-Agent 编排。
- 微服务、消息队列、Kubernetes 或工作流引擎。
- 在线训练基础模型。
- Shell、任意文件系统和任意 SQL Tool。
- 在 Phase 2C 中实现健康领域数据库、长期 Memory、Safety Guard 或写操作 Tool。

## 待确认

- `OPEN`：Phase 2C 首版是否包含 Session 列表和删除命令。
- `OPEN`：对话上下文预算与摘要触发阈值。
- `OPEN`：正式客户端采用 Flutter、Web 或其它形态。
- `OPEN`：健康领域本地持久化采用 SQLite、PostgreSQL 或其它方案。
- `OPEN`：模型调用数据保留周期。
- `OPEN`：提醒静默时段和主动询问次数上限。
- `NEEDS_TECHNICAL_SPIKE`：健康设备数据接入方式。
- `NEEDS_MEDICAL_REVIEW`：具体安全阈值和规则依据。
