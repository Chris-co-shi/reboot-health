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
Agent Runtime 负责模型回合、上下文、工具调度、运行限制和错误收敛；
确定性代码负责工具执行、数据校验、安全阻断、确认、持久化、幂等和审计。
```

项目不采用固定 Planner → Executor → Reviewer → Publisher 流水线，也不默认采用多 Agent、DAG、工作流引擎、消息队列或微服务。

历史 `backend/`、`clients/flutter/`、`frontend/` 和 `deploy/` 仍保留在仓库中，但属于 legacy，不是当前产品调用链，也不得在没有独立迁移任务时继续扩展。

长期决策见 [`decisions/0010-python-modular-monolith-and-agent-loop.md`](decisions/0010-python-modular-monolith-and-agent-loop.md)。

## 2. 总体结构

```text
CLI / future API
      ↓
Composition Root / Bootstrap
      ↓
Agent Runtime
├── Runtime Environment
├── Message History
├── Model Turn
├── Tool Call Loop
├── Limits / Timeout
├── Error Convergence
└── Trace / Events
      ↓
ModelProvider              Tool Runtime
├── OpenAI-compatible      ├── ToolRegistry
├── Message Conversion     ├── ToolExecutor
├── Tool Schema            └── Tool Handlers
└── Response Parsing              ↓
                              Domain Services
                                   ↓
                              Repository Ports
                                   ↓
                          Persistence Adapters（后续）
```

当前 Phase 2A 只建设到只读 Tool Runtime，不接数据库、写操作、安全规则引擎或确认恢复。

## 3. 依赖方向

```text
interfaces
    ↓
runtime
    ↓
model/tool/session/safety ports
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
- Tool 可以调用 Domain Service，但 Agent Loop 不直接调用数据库。
- Persistence Adapter 只能依赖 Repository Port，不反向控制 Runtime。
- 外部入口只通过 Bootstrap 获取已组装对象，不在入口内重复组装 Provider 或 Tool。

## 4. Composition Root

`health_agent/agent/bootstrap.py` 是唯一产品组装入口。

职责：

```text
加载并校验 LLMSettings
→ 创建 OpenAICompatibleProvider
→ 创建 ToolRegistry
→ 注册产品工具
→ 创建 ToolExecutor
→ 创建 AgentLoop / AgentCore
```

约束：

- `.env` 只由 Bootstrap 或其直接调用的配置加载函数读取。
- shell 环境变量优先于 `health_agent/.env`。
- 产品 Bootstrap 不导入 `tests/`、MockProvider 或 ScriptedModelProvider。
- Provider、Runtime、Skill 和 Tool 不自行创建 Provider。

## 5. Agent Runtime

### 5.1 通用请求

通用 Runtime 接受自然语言请求和通用调用元数据，不要求 trigger 映射到固定业务 Skill。

```text
AgentRequest
├── user_text
├── session_id（可选）
├── locale
└── metadata
```

本阶段 Session 只存在于进程内，不持久化、不恢复长期对话。

### 5.2 Runtime Environment

日期与时区只允许一个真相源：

```text
runtimeEnvironment.currentDate
runtimeEnvironment.currentDateTime
runtimeEnvironment.timezone
runtimeEnvironment.locale
```

通用 Context 不再独立暴露 `today`。旧兼容层如需要该字段，只能从 `runtimeEnvironment.currentDate` 派生。

### 5.3 有限轮次 Agent Loop

目标运行链路：

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

- 无 Tool Call 时立即结束。
- 同一 assistant 回合可返回多个 Tool Call，本阶段顺序执行。
- 所有 Tool Result 追加后再进入下一次 Model Turn。
- 不自动重试 Provider。
- 不自动重试失败 Tool。
- 不允许无限循环。
- 空 content 且无 Tool Call 属于无效响应。

Phase 2A 的详细算法、测试矩阵和文件级实施顺序见 [`implementation/phase-2a-read-only-tool-call-loop.md`](implementation/phase-2a-read-only-tool-call-loop.md)。

## 6. Model Provider

当前只支持 OpenAI-compatible Chat Completions。

Provider 职责：

- 转换 system/user/assistant/tool 消息。
- 转换模型可见 Tool Schema。
- 解析 assistant content 与 Tool Call。
- 保留 Tool Call id、name、raw arguments 和解析后 arguments。
- 返回 usage、finish reason 和必要 provider metadata。
- 归一化配置、网络、鉴权、限流、超时和响应协议错误。

Provider 不负责：

- Tool 执行。
- PlanningOutput 解析。
- Skill 选择。
- `.env` 加载。
- 数据库访问。
- 自动重试和 Mock 回退。

## 7. Message Contract

ModelMessage 支持：

```text
system
user
assistant
tool
```

关键不变量：

- assistant 消息可携带 `tool_calls`。
- tool 消息必须携带对应 `tool_call_id`。
- Tool Result 必须作为 role=tool 消息，不得伪装成 user 消息。
- 同一 assistant 回合多个 Tool Call 的结果顺序与请求顺序一致。

## 8. Tool Runtime

### 8.1 Tool Contract

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

模型只能看到 name、description 和 input schema，不得看到 handler、内部 Python 路径或密钥。

### 8.2 ToolRegistry

职责：

- 白名单注册。
- 工具名称唯一性校验。
- 按名称查找。
- 输出模型可见 Tool Definition。

Registry 不执行工具，也不进行健康业务判断。

### 8.3 ToolExecutor

职责：

- 校验工具存在。
- 校验权限和副作用等级。
- 校验 arguments。
- 调用 handler。
- 标准化为合法 JSON Tool Result。
- 隐藏 traceback 和内部实现细节。

### 8.4 Phase 2A 权限边界

Phase 2A 只允许只读查询或纯计算 Tool。

以下能力不进入本阶段：

```text
写操作
提案发布
确认后执行
计划发布
用户档案修改
数据库写入
```

第一个正式内置工具是 `convert_weight_unit`，只完成 kg、lb、jin 的确定性单位换算，不进行 BMI、医学或训练判断。

## 9. Tool Error 与 Runtime Error

可作为 Tool Result 返回模型的错误：

```text
unknown_tool
invalid_arguments
tool_execution_failed
invalid_tool_result
```

Provider 网络、鉴权、限流、超时和协议错误不伪装成 Tool Result，直接收敛为 `MODEL_ERROR`。

运行限制到达时返回 `LIMIT_REACHED`，并在 Trace 中记录限制类型，不记录完整 Prompt 或健康原文。

## 10. 运行限制

Phase 2A 默认建议：

```text
max_model_turns = 6
max_tool_calls = 8
timeout_seconds = 60
```

这些参数必须大于合法下限，并在 Runtime 创建时校验。

本阶段使用同步执行，不引入 asyncio、后台 worker 或消息队列。

## 11. INITIAL_PLANNING 兼容层

`INITIAL_PLANNING` 当前只是 legacy compatibility adapter：

- 可以保留旧 Planning Prompt、Input、Output 和 Schema。
- 只能通过显式兼容入口调用。
- 不再作为普通用户请求默认路径。
- 不得反向要求通用 Runtime 使用 Program、Phase、WeeklyPlan 或 TodayAction。
- 后续通用工具和领域能力成熟后再单独移除。

## 12. Safety 与 Confirmation

Phase 2A 不实现完整 Safety Guard 和 Confirmation Resume，但长期边界已经确定：

```text
Input Guard
Pre-Tool Guard
Pre-Publish Guard
Pre-Output Guard
```

Safety 不能只作为模型可选 Tool。

Confirmation 也不是普通 Tool，而是 Runtime 暂停与恢复协议：

```text
RUNNING
→ PENDING_CONFIRMATION
→ CONFIRMED / REJECTED
→ RESUMED
```

这些能力必须在后续独立阶段实现，不得在 Phase 2A 中提前创建半成品状态机。

## 13. Persistence 与领域迁移

后续 Python 模块化单体需要逐步迁移并保留旧实现中的关键语义：

- PlanVersion 不可变发布语义。
- revision 并发控制。
- 幂等键与重复请求处理。
- 确认快照。
- 追加写审计。
- 已确认事实与模型候选的区分。

在这些语义完成 Python 迁移前，不应声称 legacy 后端已可安全删除。

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

禁止记录：

```text
API key
Authorization header
完整用户健康原文
完整 prompt
raw model response
Python traceback（对用户或模型）
```

## 15. 非目标

当前架构不引入：

- 微服务。
- 消息队列。
- Kubernetes。
- 默认多 Agent 或 Subagent。
- DAG/工作流引擎。
- Shell、任意文件系统或任意 SQL Tool。
- 未经确认的医学诊断或治疗能力。

## 16. 文档边界

- 产品定位与范围：[`product-scope.md`](product-scope.md)
- 当前实施阶段与状态：[`mvp-exec-plan.md`](mvp-exec-plan.md)
- Phase 2A 实施交接：[`implementation/phase-2a-read-only-tool-call-loop.md`](implementation/phase-2a-read-only-tool-call-loop.md)
- 业务语义与不变量：[`domain-model.md`](domain-model.md)
- 安全规则：[`safety-rules.md`](safety-rules.md)
- 已确认决策：[`decisions/`](decisions/README.md)
