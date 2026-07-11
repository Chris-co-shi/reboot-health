# 架构方案

## 1. 当前架构定位

`reboot-health` 正在迁移为 **Python-first 模块化单体健康 Agent**。

当前与目标真实运行目录均为：

```text
health_agent/
```

核心原则：

```text
LLM 负责理解用户任务并决定下一步动作；
Agent Runtime 负责模型回合、消息历史、工具调度、运行限制和暂停恢复协议；
确定性代码负责工具执行、数据校验、安全阻断、确认、持久化、幂等和审计。
```

项目不采用固定 Planner → Executor → Reviewer → Publisher 流水线，也不默认采用多 Agent、DAG、工作流引擎、消息队列或微服务。

历史 `backend/`、`clients/flutter/`、`frontend/` 和 `deploy/` 属于 legacy，不是当前产品调用链。

长期决策：

- [`decisions/0010-python-modular-monolith-and-agent-loop.md`](decisions/0010-python-modular-monolith-and-agent-loop.md)
- [`decisions/0011-session-context-memory-boundaries.md`](decisions/0011-session-context-memory-boundaries.md)

## 2. 当前实现状态

```text
DONE：
- OpenAI-compatible Provider
- GenericAgentLoop
- 只读 ToolRegistry / ToolExecutor
- convert_weight_unit
- 单次 Run 内模型与工具多回合

DONE_EXPLICIT：
- JSON Session / PendingAction Store
- ConfirmationCoordinator
- lease / heartbeat / fencing
- execution checkpoint
- stale recovery
- orphan PendingAction maintenance

NEXT：
- Interactive Session CLI
- 产品入口显式接入 JSON Store
- 连续对话与跨进程 Session 恢复
```

当前默认 `agent.main` 和 `scripts/agent_console.py` 是 one-shot 入口：每次进程只接受一次用户输入，进程之间不共享消息历史。

## 3. 总体结构

```text
CLI / future API
      ↓
Composition Root / Bootstrap
      ↓
Agent Runtime
├── Runtime Environment
├── Session Message History
├── Model Turn
├── Tool Call Loop
├── Confirmation / Resume Protocol
├── Lease / Fence / Checkpoint
├── Limits / Timeout
├── Error Convergence
└── Trace / Events
      ↓
ModelProvider              Tool Runtime
├── OpenAI-compatible      ├── ToolRegistry
├── Message Conversion     ├── ToolExecutor
├── Tool Schema            └── Tool Handlers
└── Response Parsing              ↓
                              Domain Query/Command Services
                                      ↓
                                Repository Ports
                                      ↓
                              Persistence Adapters
```

当前代码已建设 Runtime 与本地 JSON Adapter；健康领域 Repository、Domain Service 和正式数据库仍属于后续阶段。

## 4. 依赖方向

```text
interfaces
    ↓
runtime
    ↓
model / tool / session / safety ports
    ↓
tool implementations / domain services
    ↓
repository ports
    ↑
persistence adapters
```

约束：

- Runtime 不包含健康业务术语、医疗阈值或训练规则。
- Provider 不依赖 Planning、Program、Phase、WeeklyPlan 或 TodayAction。
- Tool 可以调用 Domain Service，但 Agent Loop 不直接访问数据库。
- Persistence Adapter 实现 Repository Port，不反向控制 Runtime。
- 外部入口只能通过 Bootstrap 获取已组装对象。
- Session Store 与健康领域 Repository 是两类不同持久化职责。

## 5. Composition Root

`health_agent/agent/bootstrap.py` 是唯一产品组装入口。

当前职责：

```text
加载并校验 LLMSettings
→ 创建 OpenAICompatibleProvider
→ 创建 ToolRegistry
→ 注册正式只读工具
→ 创建 ToolExecutor
→ 创建 Session/PendingAction Store
→ 创建 GenericAgentLoop
→ 创建 ConfirmationCoordinator
```

约束：

- `.env` 只由 Bootstrap 或其直接调用的配置加载函数读取。
- shell 环境变量优先于 `health_agent/.env`。
- 产品 Bootstrap 不导入 `tests/`、MockProvider 或 ScriptedModelProvider。
- JSON Store 必须显式配置目录，不得无意改变默认产品行为。

## 6. Agent Runtime

### 6.1 通用请求

```text
AgentRequest
├── user_text
├── session_id（可选）
├── locale
└── metadata
```

`session_id` 是用户消息连续性的关联键。相同 `session_id` 可以在同一 Store 中追加新的用户消息。

当前 one-shot CLI 每次进程重新创建内存 Store，因此即使 Runtime 支持 `session_id`，不同命令之间仍没有会话连续性。

### 6.2 Runtime Environment

日期与时区只有一个真相源：

```text
runtimeEnvironment.currentDate
runtimeEnvironment.currentDateTime
runtimeEnvironment.timezone
runtimeEnvironment.locale
```

通用 Context 不独立暴露 `today`。legacy 兼容层只能从 `runtimeEnvironment.currentDate` 派生。

### 6.3 有限轮次 Agent Loop

```text
User Message
→ Model Turn
→ Assistant content 或 Tool Call
→ Tool 校验与执行
→ role=tool Result
→ 下一次 Model Turn
→ Final content
```

约束：

- 无 Tool Call 时立即结束当前 Run。
- 同一 assistant 回合可返回多个 Tool Call，当前按顺序执行。
- 所有 Tool Result 必须以 `role=tool` 返回模型。
- Provider 和 Tool 不自动无限重试。
- 空 content 且无 Tool Call 属于无效响应。
- 达到轮次、工具次数或超时限制时 fail-closed。

### 6.4 Session 生命周期

AgentSession 保存：

- 消息历史。
- 当前状态。
- PendingAction 指针。
- continuation。
- active run ownership。
- lease、heartbeat 和 fence generation。
- execution checkpoint。

Session 状态属于 Runtime 技术状态，不等同于 UserProfile、Plan、TrainingRecord 等健康领域事实。

### 6.5 Confirmation 与 Recovery

Confirmation 是 Runtime 暂停恢复协议，不是普通模型 Tool：

```text
RUNNING
→ WAITING_CONFIRMATION
→ APPROVED / REJECTED
→ ACTIVE
→ resume
```

当前底层协议已经实现，但默认 CLI/API 尚未提供批准、拒绝和恢复命令，也没有正式写操作 Tool。

stale recovery 采用保守策略：

- `DRIVE_READY`：可安全接管并继续。
- `MODEL_CALL_IN_FLIGHT`：状态未知，不自动重放。
- `TOOL_CALL_IN_FLIGHT`：状态未知，不自动重放。
- `FINALIZING`：终态未知，不自动覆盖。

## 7. Session、Context、Memory 与领域事实

必须严格区分：

| 概念 | 作用 | 是否为健康事实 |
|---|---|---:|
| Session Message History | 保存用户与模型当前会话消息 | 否 |
| Runtime Environment | 当前日期、时区、locale 等运行信息 | 否 |
| Conversation Summary | 为控制上下文长度生成的对话摘要 | 否 |
| UserProfile / HealthConstraint / Goal / Plan | 经确认的结构化业务事实 | 是 |
| Memory Candidate | 模型推断的行为模式或策略经验候选 | 否，确认前不得生效 |

规则：

- Conversation Summary 不能自动写成 UserProfile 或 HealthConstraint。
- 用户健康事实必须通过领域模型、Repository 和确认边界管理。
- 普通澄清问题不创建 PendingAction。
- 模型不得把单次推断自动变成长期 Memory。

## 8. Phase 2C 目标架构

```text
scripts/agent_chat.py
→ create_generic_runtime_components_from_env(...)
→ 固定当前 session_id
→ 循环读取用户输入
→ components.loop.run(AgentRequest(...))
→ 输出最终回答
→ /new /resume /status /exit
```

内存模式用于单次进程体验；JSON 模式用于退出后恢复。

Phase 2C 只解决 Conversation Continuity，不引入健康领域数据、数据库、Safety Guard 或写操作 Tool。

## 9. Model Provider

当前只支持 OpenAI-compatible Chat Completions。

Provider 负责：

- 转换 system/user/assistant/tool 消息。
- 转换模型可见 Tool Schema。
- 解析 assistant content 与 Tool Call。
- 保留 Tool Call id、name 和 arguments。
- 返回 usage、finish reason 和必要 metadata。
- 归一化配置、网络、鉴权、限流、超时和协议错误。

Provider 不负责 Tool 执行、Skill 选择、数据库访问、`.env` 加载或自动重试。

## 10. Tool Runtime

每个产品 Tool 至少声明：

```text
name
description
input_schema
output_schema
permission
side_effect
timeout_seconds
handler
```

ToolRegistry 负责白名单和模型可见定义；ToolExecutor 负责查找、校验、执行和结构化结果。

当前正式产品 Tool 仍只允许只读查询或纯计算，不允许未经独立阶段批准新增写操作、任意 SQL、任意文件系统或 shell Tool。

## 11. 健康领域 Read Model

Phase 3A 计划通过以下链路读取真实业务数据：

```text
Read-only Tool
→ Domain Query Service
→ Repository Port
→ Persistence Adapter
```

候选 Read Model：

- UserProfile。
- HealthConstraint。
- Goal。
- CurrentPlanView。
- TrainingRecord / DailyActionExecution。
- Observation。
- ExecutionSummary。

Agent Runtime 不直接知道这些模型的持久化细节。

## 12. Safety 与受控写入

完整 Safety Guard 必须由确定性代码实现：

```text
Input Guard
Pre-Tool Guard
Pre-Proposal / Pre-Publish Guard
Pre-Output Guard
```

写入流程必须区分：

```text
Clarification：普通补充信息
Proposal：未执行候选
Confirmation：用户批准高影响写入或发布
```

Safety、Confirmation、幂等和审计不能仅依赖 Prompt 或模型自觉。

## 13. Persistence 与领域迁移

后续 Python 模块化单体需要迁移并保留：

- PlanVersion 不可变发布语义。
- revision 并发控制。
- 幂等键与重复请求处理。
- 确认快照。
- 追加写审计。
- 已确认事实与模型候选的区分。

在这些语义完成 Python 迁移前，不应声称 legacy 后端可以安全删除。

## 14. 可观测性

RunTrace 只记录运行摘要：

```text
run/session id
provider
model turn count
tool call count
tool names
finish reason
limit/error category
latency
usage summary
```

禁止记录 API Key、Authorization header、完整用户健康原文、完整 Prompt、raw model response 或对用户暴露的 Python traceback。

## 15. 非目标

当前不建设：

- 固定多角色流水线。
- 默认多 Agent 编排。
- 微服务与消息队列。
- 任意代码执行工具。
- 未经确认的健康事实写入。
- 模型自动修改计划或增加训练风险。
