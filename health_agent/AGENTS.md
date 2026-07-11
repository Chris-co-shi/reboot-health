# Python Health Agent Runtime 规则

## 定位

`health_agent/` 是 reboot-health 当前与目标 Python 模块化单体 Runtime。

当前重构方向由以下文档共同约束：

```text
../docs/architecture.md
../docs/mvp-exec-plan.md
../docs/decisions/0010-python-modular-monolith-and-agent-loop.md
```

Phase 2A 的工程交接与验收参考：

```text
../docs/implementation/phase-2a-read-only-tool-call-loop.md
```

未经用户明确要求，不在本目录任务中修复旧 Java/Python HTTP 链路，也不修改 Flutter、Vue 或 Compose。

## 当前阶段

- Phase 1、1.1、1.2、1.3 已完成。
- 产品运行 Provider 是真实 OpenAI-compatible `ModelProvider.complete_turn(...)`。
- `INITIAL_PLANNING` 是已验证且已隔离的显式 legacy compatibility adapter。
- Phase 2A 通用只读 Tool Call Agent Loop 已完成并经过真实 LLM Tool Call 验收。
- Phase 2B Runtime 确认、恢复与 JSON 持久化基础已完成显式能力；默认产品入口仍使用内存 Store。
- PostgreSQL、Redis、FastAPI、Memory、产品级 Safety Guard、Console/API Confirmation 入口、Plan Publish、多 Agent、MCP、消息队列和向量数据库尚未接入。

## Phase 2A 任务合同

开始修改前必须声明：

```text
Primary Module:
  health_agent 通用 Agent Runtime 与只读 Tool Call Loop

Allowed Paths:
  agent/runtime/
  agent/models/
  agent/tools/
  agent/bootstrap.py
  agent/main.py
  scripts/agent_console.py
  prompts/
  tests/
  README.md
  AGENTS.md

Conditional Compatibility Path:
  agent/skills/initial_planning.py
  只允许为隔离兼容入口做最小修改。

Forbidden Paths:
  ../backend/
  ../clients/flutter/
  ../frontend/
  ../deploy/docker-compose.yml

Out of Scope:
  FastAPI、数据库、Memory、Safety Guard、Confirmation、Plan Publish、
  DailyRecord、写操作 Tool、多 Agent、Subagent、DAG、工作流引擎、消息队列。
```

## Runtime 边界

Agent Runtime 只负责：

- 通用请求归一化。
- Runtime Environment。
- Message History。
- Model Turn。
- Tool Call Loop。
- 最大模型回合和最大 Tool Call 数。
- 整体超时。
- 错误收敛。
- RunTrace。
- Session/Confirmation 协议边界、运行租约、checkpoint 和恢复分类。

Runtime 不得包含：

- 训练规则。
- 血压、疼痛、饮食或医学判断。
- Program、Phase、WeeklyPlan、TodayAction。
- 数据库访问。
- 用户健康事实硬编码。
- 写操作执行、业务确认决策或发布策略。

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

Phase 2A 必须支持：

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
- 同一 assistant 回合的所有 Tool Result 追加后，才能进入下一次 Model Turn。

## Tool Runtime 边界

### ToolRegistry

只负责：

- 白名单注册。
- 工具名称非空和唯一性校验。
- 按名称查找。
- 输出模型可见 name、description 和 input schema。

不得执行 Tool，不得暴露 handler、Python 路径或内部类名。

### ToolExecutor

只负责：

- 查找注册工具。
- 校验 READ_ONLY 权限和无副作用边界。
- 校验 arguments。
- 调用 handler。
- 输出合法 JSON Tool Result。
- 将 unknown_tool、invalid_arguments、tool_execution_failed、invalid_tool_result 返回模型。

不得：

- 执行未注册工具。
- 使用 shell、任意文件系统或任意 SQL。
- 输出 Python traceback 给模型。
- 自动重试失败 Tool。
- 把失败结果伪装成成功。

### Phase 2A 工具权限

只允许：

```text
READ_ONLY
```

如果现有枚举名为 `READ`，只能表达无持久化副作用的查询或纯计算。

不得注册：

```text
WRITE
LOW_RISK_WRITE
CONFIRMATION_REQUIRED
PROPOSAL
PUBLISH
FORBIDDEN
```

首个正式产品 Tool 是 `convert_weight_unit`，只支持 kg、lb、jin 的确定性换算，不做 BMI、医学或训练判断。

## Runtime Environment

通用 Context 只保留：

```text
runtimeEnvironment.currentDate
runtimeEnvironment.currentDateTime
runtimeEnvironment.timezone
runtimeEnvironment.locale
```

不再向通用 Runtime 暴露独立 `today`。`INITIAL_PLANNING` 如需要，只能在兼容适配器内部派生。

时间必须可注入，以便测试不依赖机器当前时间。

## INITIAL_PLANNING 兼容层

- 只能作为显式 legacy 入口保留。
- 普通用户请求不得默认通过 trigger 进入该 Skill。
- 通用 AgentLoop 不得导入 PlanningOutput、Program、Phase 或 WeeklyPlan。
- 兼容层不得反向要求通用 Runtime 使用固定 Planning 工作流。
- 本阶段不删除 Planning 业务结构，也不借机重写计划逻辑。

## Bootstrap

唯一产品组装顺序：

```text
LLMSettings
→ OpenAICompatibleProvider
→ ToolRegistry
→ 注册内置只读工具
→ ToolExecutor
→ AgentLoop
→ AgentCore / 产品入口
```

Bootstrap 不得导入 `tests/`、ScriptedModelProvider、MockProvider、Fake Tool 或 Smoke Tool。

## 测试规则

- 普通 unittest 不允许调用真实模型、网络、数据库或外部服务。
- ScriptedModelProvider 只能位于 `tests/support/`。
- 测试替身不得包含健康计划业务逻辑。
- Phase 2A 必须覆盖直接回答、单 Tool Call、多 Tool Call、未知工具、参数非法、Tool 异常、非法 Tool 结果、空响应、最大模型回合、最大工具次数和消息顺序。
- 真实 LLM 验收必须确认原生 Tool Call、role=tool Result、至少两次模型回合和不经过 `INITIAL_PLANNING`。

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
- 完整 prompt。
- raw model response。
- API key、Authorization header 或令牌。
- 对用户或模型暴露的 Python traceback。

## 禁止

- 不开放 shell Tool、任意文件系统 Tool 或任意 SQL Tool。
- 不连接 PostgreSQL、SQLite 或 Redis。
- 不新增其他模型供应商框架。
- 不实现写操作、Safety Guard、Confirmation、Plan Publish 或 Memory 半成品。
- 不通过普通文本解析伪 Tool Call。
- 不新增多 Agent、Subagent、DAG 或工作流引擎。
- 不为了测试通过而删除测试、放宽断言、绕过校验或降低规则。
- 不记录真实健康资料、密钥、令牌或认证信息。

## 验证命令

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests -v

git diff --check
```

产品路径替身检查：

```bash
rg "MockProvider|ScriptedModelProvider" agent scripts
```

任意执行能力检查：

```bash
rg "eval\\(|exec\\(|subprocess|os\\.system" agent/tools agent/runtime
```

真实验收输入与完整 Definition of Done 见 Phase 2A 实施规范。
