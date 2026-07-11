# Python Health Agent Runtime 规则

## 定位

`health_agent/` 是 reboot-health 当前与目标 Python 模块化单体 Runtime。

当前重构方向由以下文档共同约束：

```text
../docs/architecture.md
../docs/mvp-exec-plan.md
../docs/decisions/0010-python-modular-monolith-and-agent-loop.md
../docs/decisions/0011-session-context-memory-boundaries.md
```

当前 Phase 2C 工程交接：

```text
../docs/implementation/phase-2c-interactive-session-cli.md
```

已完成 Phase 2A 验收参考：

```text
../docs/implementation/phase-2a-read-only-tool-call-loop.md
```

未经用户明确要求，不修复旧 Java/Python HTTP 链路，也不修改 Flutter、Vue 或 Compose。

## 当前阶段

- Phase 1、1.1、1.2、1.3 已完成。
- 产品 Provider 是真实 OpenAI-compatible `ModelProvider.complete_turn(...)`。
- `INITIAL_PLANNING` 是已验证且隔离的显式 legacy compatibility adapter。
- Phase 2A 通用只读 Tool Call Agent Loop 已完成并经过真实 LLM Tool Call 验收。
- Phase 2B Runtime 状态、确认、恢复与 JSON 持久化安全基础已完成显式能力。
- Phase 2C Interactive Session & Conversation Context 已完成并经过真实 LLM 连续对话与 JSON 恢复验收。
- 默认 `agent.main` 和 `scripts/agent_console.py` 仍是 one-shot、内存 Store 入口；`scripts/agent_chat.py` 是显式交互式 Session CLI。
- 当前后续阶段是 Phase 3A 健康领域 Read Model、Repository Port 与只读工具，但仍为 TODO，进入前需要独立任务确认。
- PostgreSQL、SQLite、Redis、FastAPI、健康领域 Repository、长期 Memory、产品级 Safety Guard、正式写操作和 Plan Publish 尚未接入。

## Phase 2C 任务合同

维护 Phase 2C 交互式 Session CLI 或相关 Runtime Store 组装前必须声明：

```text
Primary Module:
  health_agent 交互式 Session CLI 与现有 Runtime Store 组装

Allowed Paths:
  scripts/agent_chat.py
  agent/bootstrap.py
  agent/main.py（仅共享展示/错误辅助的最小调整）
  agent/runtime/（仅修复 Phase 2C 验收暴露的通用 Session 问题）
  tests/
  README.md
  AGENTS.md
  ../README.md
  ../docs/mvp-exec-plan.md
  ../docs/architecture.md
  ../docs/implementation/phase-2c-interactive-session-cli.md

Forbidden Paths:
  ../backend/
  ../clients/flutter/
  ../frontend/
  ../deploy/

Out of Scope:
  FastAPI
  数据库、Redis、消息队列
  健康领域 Repository
  UserProfile/HealthConstraint/Plan 持久化
  长期 Memory 自动提取
  Safety Guard
  正式写操作 Tool
  Plan Publish
  多 Agent/Sub-Agent/DAG
```

## Runtime 边界

Agent Runtime 负责：

- 通用请求归一化。
- Runtime Environment。
- Session Message History。
- Model Turn。
- Tool Call Loop。
- 最大模型回合和最大 Tool Call 数。
- 整体超时。
- 错误收敛。
- RunTrace。
- Session/Confirmation 协议。
- lease、heartbeat、fence、checkpoint 和 recovery classification。

Runtime 不得包含：

- 训练规则。
- 血压、疼痛、饮食或医学判断。
- Program、Phase、WeeklyPlan、TodayAction。
- 健康领域数据库访问。
- 用户健康事实硬编码。
- 把 Conversation Summary 写成领域事实。
- 自动长期 Memory。
- 正式业务写入和发布策略。

## Phase 2C 实现规则

### 复用 Runtime Components

交互式 CLI 必须只创建一次：

```python
components = create_generic_runtime_components_from_env(...)
```

输入循环必须复用同一组：

- `loop`。
- `session_store`。
- `pending_action_store`。
- `confirmation_coordinator`。

不得每轮输入重新组装 Provider、Registry 或 Store。

### Session ID

- 每个交互式 CLI 维护当前 `session_id`。
- 普通用户输入使用同一 `session_id` 调用 `loop.run(...)`。
- `/new` 创建新 Session，不覆盖旧 Session。
- `/resume <session-id>` 只切换到已存在 Session。
- Session 不存在时不得调用模型。

### Storage

允许：

```text
memory
json
```

- 默认使用 memory。
- json 必须显式提供目录。
- 不读取环境变量隐式启用磁盘 Store。
- JSON 明文风险必须在 CLI/README 中明确提示。

### Clarification 与 Confirmation

```text
Clarification：普通下一轮 user message
Proposal：未执行候选
Confirmation：高影响 Tool、写入或发布审批
```

普通澄清问题不得创建 PendingAction，也不得把用户随后的自然语言视为隐式 approve。

### CLI 命令

首版必须支持：

```text
/help
/new
/status
/resume <session-id>
/exit
```

未知命令不得发送给模型。

## ModelProvider 边界

Provider 只负责：

- 调用 OpenAI-compatible Chat Completions。
- 转换 system/user/assistant/tool 消息。
- 转换模型可见 Tool Schema。
- 解析 assistant content、Tool Call、usage 和 finish reason。
- 归一化配置、网络、鉴权、限流、超时和协议错误。

Provider 不得：

- 读取 `.env` 或 `os.environ`。
- 执行 Tool。
- 解析 PlanningOutput。
- 选择 Skill。
- 自动重试或回退测试替身。
- 知道 Program、Phase、WeeklyPlan、TodayAction、PlanVersion 或 HealthConstraint。

产品 Provider 必须通过 `agent/bootstrap.py` 显式注入。

## Message Contract

必须支持：

```text
system
user
assistant
tool
```

不变量：

- assistant 可携带一个或多个 `tool_calls`。
- tool 消息必须关联对应 `tool_call_id`。
- Tool Result 不得伪装成 user 消息。
- 同一 assistant 回合的 Tool Result 全部追加后才能进入下一次 Model Turn。
- 同一 Session 的新 user message 必须追加在已有消息历史之后。

## Tool Runtime 边界

ToolRegistry 只负责白名单、唯一性、查找和模型可见定义。

ToolExecutor 只负责：

- 查找注册工具。
- 校验权限和副作用。
- 校验 arguments。
- 调用 handler。
- 输出合法 JSON Tool Result。
- 将 unknown_tool、invalid_arguments、tool_execution_failed 和 invalid_tool_result 返回模型。

不得：

- 执行未注册工具。
- 使用 shell、任意文件系统或任意 SQL。
- 输出 Python traceback 给模型。
- 自动重试失败 Tool。
- 把失败结果伪装成成功。

当前正式产品 Tool 仍只允许 READ_ONLY 或纯计算能力。

## Session、Context、Memory 边界

```text
Session Message History：连续对话技术状态
Runtime Context：当前模型输入
Conversation Summary：上下文压缩
Domain Facts：结构化健康事实
Memory Candidate：模型推断候选
```

规则：

- Conversation Summary 不得成为 UserProfile、HealthConstraint 或 Goal。
- 重要健康事实必须由后续领域服务和确认边界管理。
- Memory Candidate 确认前不得生效。
- Session 删除不得隐式删除领域事实。

## INITIAL_PLANNING 兼容层

- 只能作为显式 legacy 入口保留。
- 普通用户请求不得默认通过 trigger 进入该 Skill。
- GenericAgentLoop 不得导入 PlanningOutput、Program、Phase 或 WeeklyPlan。
- 兼容层不得反向要求通用 Runtime 使用固定 Planning 工作流。

## Bootstrap

唯一产品组装顺序：

```text
LLMSettings
→ OpenAICompatibleProvider
→ ToolRegistry
→ 注册内置只读工具
→ ToolExecutor
→ Session/PendingAction Store
→ GenericAgentLoop
→ ConfirmationCoordinator
```

Bootstrap 不得导入 `tests/`、ScriptedModelProvider、MockProvider、Fake Tool 或 Smoke Tool。

## 测试规则

普通 unittest 不允许调用真实模型、网络、数据库或外部服务。

Phase 2C 必须覆盖：

- 两轮输入使用同一 Session。
- 第二轮模型消息包含第一轮 user/assistant。
- `/new` 隔离消息历史。
- `/resume` 恢复已有 Session。
- JSON 模式重建 Runtime 后恢复 Session。
- 未知命令不发送给模型。
- one-shot main/console 不回归。
- 现有 Tool Call、lease、checkpoint、recovery 和 orphan 测试继续通过。

真实 LLM 验收必须确认：

- 第二轮回答记得第一轮用户目标。
- JSON 模式跨进程恢复。
- 未虚构用户档案或历史记录。
- 未经过 `INITIAL_PLANNING`。

## 日志与 Trace

RunTrace 可以记录：

- provider。
- 模型回合数。
- Tool Call 数。
- 工具名称。
- finish reason。
- 限制或错误分类。
- latency 和 usage 摘要。

禁止记录：

- 完整健康原文。
- 完整 Prompt。
- raw model response。
- API Key、Authorization header 或令牌。
- 对用户或模型暴露的 Python traceback。

## 禁止

- 不开放 shell、任意文件系统或任意 SQL Tool。
- 不连接健康领域数据库。
- 不新增模型供应商框架。
- 不实现写操作、Safety Guard、Plan Publish 或长期 Memory 半成品。
- 不通过普通文本解析伪 Tool Call。
- 不新增多 Agent、Sub-Agent、DAG 或工作流引擎。
- 不为了测试通过而删除测试、放宽断言、绕过校验或降低规则。
