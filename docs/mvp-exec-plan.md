# MVP 执行计划

本文档是当前阶段、状态、范围、验收结果和下一步的唯一事实来源。

历史 Java/Flutter 多运行时里程碑不再作为当前开发路线；相关代码和文档仅保留为 legacy 与迁移参考。

## 1. 状态约定

| 状态 | 含义 |
|---|---|
| `DONE` | 自动化验证和要求的真实运行验收均完成 |
| `DONE_EXPLICIT` | 自动化验收完成，但能力需要显式启用或调用，尚非默认产品流程 |
| `READY` | 设计、范围和验收标准已确认，可以开始实现 |
| `IN_PROGRESS` | 正在实施，尚未完成全部验收 |
| `IMPLEMENTED_WITH_BLOCKERS` | 主体存在，但仍有真实环境或关键验收阻塞 |
| `TODO` | 尚未进入实施 |
| `BLOCKED` | 存在必须先解决的依赖或决策 |
| `OPTIONAL` | 不影响核心产品闭环的可选能力 |

不得把仅存在代码、只通过 Mock、只通过静态分析或未运行真实链路的能力标记为 `DONE`。

## 2. 当前总状态

```text
当前架构：Python-first 模块化单体
当前真实目录：health_agent/

已完成：
- Phase 1 / 1.1 / 1.2 / 1.3
- Phase 2A 通用只读 Tool Call Agent Loop
- Phase 2B Runtime 状态、确认、恢复与 JSON 持久化安全基础（DONE_EXPLICIT）

当前默认产品体验：
- 一次命令只接收一次用户输入
- 单次 Agent Run 内支持模型与工具多回合
- agent.main 与 agent_console.py 默认使用内存 Store
- 不同进程之间没有对话连续性

NEXT：Phase 2C Interactive Session & Conversation Context
```

当前默认产品链路：

```text
一次用户输入
→ 产品 Bootstrap
→ GenericAgentLoop
→ 真实 LLM
→ 可选只读 Tool Call
→ ToolExecutor
→ role=tool Result
→ 真实 LLM
→ 最终自然语言回答
→ 进程结束
```

Phase 2C 完成后的目标体验：

```text
启动交互式 CLI
→ 用户连续输入
→ 同一个 session_id 持续追加消息
→ 可退出并使用 JSON Store 恢复
→ Agent 能基于此前对话继续追问和回答
```

## 3. 已完成阶段

### Phase 1：真实 Provider 与通用 Model Contract

状态：`DONE`

完成内容：

- 当前 Python 主目录统一为 `health_agent/`。
- 产品运行不再默认使用 MockProvider。
- Provider 合同迁移为通用 `complete_turn(...)`。
- OpenAI-compatible Provider 支持普通文本、Tool Call、usage 和 finish reason。
- 产品 Bootstrap 显式注入真实 Provider。
- 测试替身仅存在于 `tests/`。

### Phase 1.1：LLM 配置入口收口

状态：`DONE`

完成内容：

- 环境变量统一为 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`。
- `.env` 统一位于 `health_agent/.env`。
- shell 环境变量优先于 `.env`。
- 缺少必要配置时明确失败，不回退测试替身。

### Phase 1.2：真实 LLM 接入验收

状态：`DONE`

完成内容：

- 真实 Provider 网络调用成功。
- `agent.main` 经 Bootstrap 调用真实模型。
- Provider 返回合法 `ModelResponse`。
- 进程成功退出且不泄露 API Key。

### Phase 1.3：INITIAL_PLANNING 兼容层去污染

状态：`DONE`

完成内容：

- 删除未经用户输入确认的固定健康事实注入。
- 删除 Java/Domain Kernel 主路径职责文案。
- `INITIAL_PLANNING` 仅作为显式 legacy compatibility 入口保留。
- 默认 main 和 console 不再进入固定规划流程。

### Phase 2A：通用只读 Tool Call Agent Loop

状态：`DONE`

权威验收参考：

[`implementation/phase-2a-read-only-tool-call-loop.md`](implementation/phase-2a-read-only-tool-call-loop.md)

完成内容：

- 通用 `AgentRequest` 与 `AgentRunResult`。
- system/user/assistant/tool 消息合同。
- assistant Tool Call 与 `tool_call_id` 关联。
- ToolRegistry 白名单注册与模型 Schema 输出。
- ToolExecutor 确定性只读执行。
- Tool Error 结构化返回模型。
- 最大模型回合、最大工具次数和整体超时。
- 正式产品工具 `convert_weight_unit`。
- `agent.main` 与 `scripts/agent_console.py` 默认进入 `GenericAgentLoop`。

真实验收摘要：

```text
确定性测试：145 个通过，默认跳过 2 个显式真实集成测试
真实模型调用轮数：2
真实工具调用次数：1
真实工具名称：convert_weight_unit
真实转换结果：190 jin → 95 kg
真实入口不经过 INITIAL_PLANNING
```

### Phase 2B：Runtime 状态、确认、恢复与持久化安全基础

状态：`DONE_EXPLICIT`

说明：本阶段完成的是 Runtime 底层安全协议，不代表默认 CLI 已具备连续聊天、确认交互或跨进程恢复体验。

完成内容：

- AgentSession 与 PendingAction 状态合同。
- ApprovalPolicy、ConfirmationCoordinator 与一次性批准/拒绝/恢复协议。
- 本地 JSON Session/PendingAction Store。
- CAS、跨进程锁、原子替换与安全文件键。
- RUNNING ownership、lease、heartbeat 与 fence generation。
- DRIVE_READY / MODEL_CALL_IN_FLIGHT / TOOL_CALL_IN_FLIGHT / FINALIZING checkpoint。
- stale recovery；仅 DRIVE_READY 可自动恢复，其余状态 fail-closed。
- orphan PendingAction 显式扫描与清理。

当前限制：

- 默认 `agent.main` 和 `agent_console.py` 仍使用内存 Store。
- 没有交互式聊天 CLI。
- 没有 Session 列表、恢复、删除等用户命令。
- 没有 Console/API 的批准、拒绝和恢复入口。
- 没有正式写操作 Tool。
- JSON 文件为本地明文，不声明医疗数据合规能力。

## 4. 当前阶段

### Phase 2C：Interactive Session & Conversation Context

状态：`READY`

实施规范：

[`implementation/phase-2c-interactive-session-cli.md`](implementation/phase-2c-interactive-session-cli.md)

#### 目标

让已有 GenericAgentLoop 和 JSON Runtime Store 形成第一个可直接使用的连续对话入口。

#### 范围

- 新增交互式 `scripts/agent_chat.py`。
- 单进程复用同一组 Runtime Components。
- 使用同一个 `session_id` 连续追加用户消息。
- 支持内存与显式 JSON Store。
- 支持退出后恢复指定 Session。
- 最小命令：`/help`、`/new`、`/status`、`/resume`、`/exit`。
- 对用户明确区分 one-shot CLI 与 interactive CLI。
- 为后续上下文预算和对话摘要保留稳定边界。

#### 不包含

- 用户健康档案、健康约束或训练计划持久化。
- 健康领域只读工具。
- 模型自动写入长期 Memory。
- FastAPI、数据库、Redis 或消息队列。
- 正式写操作 Tool。
- 产品级 Safety Guard。

#### 核心验收

```text
用户：帮我制定一套增肌计划，需要什么信息可以问我
Agent：提出澄清问题
用户：男，33 岁，175cm……
Agent：保留上轮目标并继续追问或回答
退出 CLI
使用同一 session_id 重新启动
Agent：恢复此前对话消息
```

必须验证：

- 同一进程的第二次用户输入能看到第一轮消息。
- JSON 模式重启后能恢复同一 Session。
- `/new` 创建全新会话，不污染旧会话。
- 不把普通澄清问题建模为 PendingAction。
- 默认 one-shot 入口行为不被破坏。
- 不把 Conversation Summary 写成已确认健康事实。

## 5. 后续阶段

### Phase 3A：健康领域 Read Model、Repository Port 与只读工具

状态：`TODO`

目标：让 Agent 读取真实、结构化、可追溯的健康业务数据。

候选范围：

- UserProfile。
- HealthConstraint。
- Goal。
- CurrentPlanView。
- TrainingRecord / DailyActionExecution。
- Observation / DailyRecord。
- ExecutionSummary。
- Repository Ports 与本地 Persistence Adapter。
- 只读工具：
  - `get_user_profile`
  - `get_health_constraints`
  - `get_current_plan`
  - `get_recent_training_records`
  - `get_recent_observations`
  - `get_execution_summary`

约束：

- Runtime 不直接访问数据库或文件。
- 用户健康事实不得硬编码到 Prompt 或 Runtime。
- Domain Facts 不得用通用 Memory 代替。
- 第一版持久化技术选择需在实施前确认。

### Phase 3B：确定性健康 Safety Guard

状态：`TODO`

范围：

- Input Guard。
- Pre-Tool Guard。
- Pre-Proposal / Pre-Publish Guard。
- Pre-Output Guard。
- 确定性 BLOCK/WARN 决策。
- 安全规则来源、版本、审计和医学审核流程。

Safety 不得仅实现成模型可选 Tool 或 Prompt 文案。

### Phase 4：Proposal、Confirmation 与受控写入

状态：`TODO`

范围：

- Proposal Tool / Domain Command Candidate。
- 内容哈希、revision、幂等和确认快照。
- 用户确认后写入健康事实、训练记录或计划草案。
- PlanVersion 发布与不可变版本语义迁移。
- 写入前 Safety Guard。

语义区分：

```text
Clarification：普通补充信息，不创建 PendingAction
Proposal：模型提出候选，尚未执行
Confirmation：用户批准高影响写入或发布
```

### Phase 5：执行记录与动态调整闭环

状态：`TODO`

范围：

- DailyAction / DailyActionExecution。
- 训练完成、部分完成、跳过。
- 体重、睡眠、疲劳、疼痛等 Observation。
- 周期执行摘要和趋势分析。
- 基于真实记录提出调整 Proposal。
- Memory Candidate 的可追溯、可确认、可纠正机制。

### Phase 6：产品 API 与客户端集成

状态：`TODO`

范围：

- FastAPI 产品入口。
- API 鉴权与隐私边界。
- Session、工具、提案、确认与记录 API。
- Flutter/Web 正式客户端选择与迁移。
- legacy Java/Flutter/Compose 下线计划。

### Phase 7：生产化、安全、评测与运维

状态：`TODO`

范围：

- CI、回归测试和真实模型评测集。
- 可观测、审计、成本与延迟指标。
- Prompt/Tool/Safety 版本管理。
- 备份、恢复、数据保留和隐私控制。
- 部署、运行手册与故障处理。

### Phase 8：高级 Agent 能力

状态：`OPTIONAL`

候选范围：

- Sub-Agent 与权限隔离。
- 异步任务和主动提醒。
- 穿戴设备与健康平台接入。
- 长周期趋势分析。

默认不引入多 Agent；只有明确出现上下文隔离、专门权限或独立任务生命周期需求时再决策。

## 6. Session、Context、Memory 与领域事实边界

详细决策见：

[`decisions/0011-session-context-memory-boundaries.md`](decisions/0011-session-context-memory-boundaries.md)

```text
Session Message History ≠ 长期 Memory
Conversation Summary ≠ 已确认健康事实
UserProfile / HealthConstraint / Plan ≠ 模型记忆
Memory Candidate ≠ 自动生效的领域事实
```

## 7. Legacy 说明

旧文档曾记录：

```text
Flutter → Java AgentRun → Python Runtime
```

该路线已由 ADR 0010 替代，不再是当前实施目标。

历史代码可以用于迁移业务语义，但不得因为旧实现存在而声称当前 Python 产品已经具备数据库、计划发布、完整 Safety、正式客户端或生产能力。

## 8. 当前未决事项

- Phase 2C Session 列表和删除能力是否进入首个 Slice。
- 对话上下文预算与摘要触发阈值。
- Phase 3A 本地持久化最终采用 SQLite、PostgreSQL 或其它方案。
- 正式客户端采用 Flutter、Web 或其它形态。
- 医疗与运动安全阈值的专业依据与审核流程。
