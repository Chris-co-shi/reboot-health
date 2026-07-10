# Phase 2A：通用只读 Tool Call Agent Loop

## 1. 文档定位

本文是 Phase 2A 的工程交接规范。目标是在不引入数据库、写操作、安全规则引擎、确认恢复或多 Agent 的前提下，建立最小但真实可运行的通用 Agent Loop。

完成后的真实链路：

```text
用户输入
→ Runtime 构建通用上下文与消息
→ OpenAI-compatible ModelProvider
→ Assistant 普通文本或原生 Tool Call
→ ToolRegistry 查找白名单工具
→ ToolExecutor 校验并执行只读工具
→ Tool Result 作为 role=tool 消息返回模型
→ 模型继续判断
→ 无 Tool Call 时返回最终自然语言结果
```

本阶段不是固定规划工作流，也不以 `INITIAL_PLANNING` 作为默认入口。

## 2. 任务契约

```text
Primary Module:
  health_agent 通用 Agent Runtime 与只读 Tool Call Loop

Allowed Paths:
  health_agent/agent/runtime/
  health_agent/agent/models/
  health_agent/agent/tools/
  health_agent/agent/bootstrap.py
  health_agent/agent/main.py
  health_agent/scripts/agent_console.py
  health_agent/prompts/
  health_agent/tests/
  health_agent/README.md
  health_agent/AGENTS.md

Conditional Compatibility Path:
  health_agent/agent/skills/initial_planning.py
  只允许为兼容入口隔离做最小调整，不改变 Planning 业务结构。

Forbidden Paths:
  backend/
  clients/flutter/
  frontend/
  deploy/docker-compose.yml

Required Verification:
  python3 -m compileall agent tests
  python3 -m unittest discover -s tests -v
  git diff --check
  产品路径测试替身搜索
  任意代码执行能力搜索
  真实 LLM Tool Call 验收

Out of Scope:
  FastAPI
  SQLite/PostgreSQL/Redis
  Memory
  Safety Guard
  Confirmation Pause/Resume
  Plan Publish
  DailyRecord
  用户档案持久化
  写操作 Tool
  多 Agent/Subagent
  DAG/工作流引擎
  消息队列
```

## 3. 已确认架构原则

1. LLM 决定直接回答还是调用可用工具。
2. Runtime 维护消息、运行限制、工具调度和错误收敛。
3. Tool 只执行确定性代码，不把业务判断塞进 Runtime。
4. Provider 只负责 OpenAI-compatible 消息与响应转换。
5. 本阶段所有产品工具必须是只读或纯计算，无持久化副作用。
6. 不通过解析普通文本中的伪工具指令模拟 Tool Call；只接受 Provider 返回的原生 Tool Call。
7. 不默认启用固定 Planner/Executor/Reviewer/Publisher 流程。
8. 不要求每个请求都调用工具。
9. 不允许无限循环、隐式重试或静默吞掉工具错误。
10. `INITIAL_PLANNING` 继续保留为 legacy compatibility adapter，但不参与通用入口。

## 4. 模块职责

### 4.1 AgentLoop

只负责：

- 构建并维护本次运行的 `ModelMessage` 列表。
- 调用 `ModelProvider.complete_turn(...)`。
- 判断响应是最终文本还是 Tool Call。
- 按顺序执行同一回合中的全部 Tool Call。
- 追加 assistant/tool 消息。
- 控制最大模型回合数、最大工具调用数和整体超时。
- 收敛 Provider、Tool 和无效响应错误。
- 返回结构化 `AgentRunResult` 与脱敏 `RunTrace`。

不得包含：

- 训练、血压、疼痛、饮食或医学规则。
- Program、Phase、WeeklyPlan、TodayAction。
- 用户健康档案查询实现。
- 数据库访问。
- 确认、发布或写操作策略。

### 4.2 ModelProvider

只负责：

- 接收完整 messages、可见 tools 和 options。
- 转换 OpenAI-compatible Chat Completions 请求。
- 正确发送 assistant tool calls 与 role=tool 消息。
- 解析 assistant content、tool calls、usage、finish reason 和 provider metadata。
- 将网络、鉴权、限流、超时和协议错误转换为 Provider 异常。

不得：

- 执行工具。
- 解析 PlanningOutput。
- 读取数据库。
- 选择 Skill。
- 读取 `.env`。
- 重试请求或回退测试替身。

### 4.3 ToolRegistry

只负责：

- 注册白名单工具。
- 校验工具名称非空且唯一。
- 按名称查找工具。
- 生成模型可见的 Tool Schema。

不得：

- 执行工具。
- 暴露 handler、Python 模块路径或内部类名。
- 做健康业务判断。

### 4.4 ToolExecutor

只负责：

- 根据 Tool Call 从 Registry 查找工具。
- 校验工具权限为只读。
- 校验参数结构。
- 调用 handler。
- 标准化为合法 JSON Tool Result。
- 将可恢复错误返回模型。

不得：

- 执行未注册工具。
- 运行 shell、任意文件或任意 SQL。
- 把 Python traceback 返回模型。
- 自动重试 handler。
- 把失败伪装成成功。

### 4.5 Bootstrap

只负责产品组装：

```text
LLMSettings
→ OpenAICompatibleProvider
→ ToolRegistry
→ 注册内置只读工具
→ ToolExecutor
→ AgentLoop
→ AgentCore/产品入口
```

产品 Bootstrap 不得导入 `tests/`、`ScriptedModelProvider` 或任何 Mock。

## 5. 通用运行合同

### 5.1 AgentRequest

建议最小合同：

```python
@dataclass(frozen=True)
class AgentRequest:
    user_text: str
    session_id: str | None = None
    locale: str = "zh-CN"
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

约束：

- `user_text` 去除首尾空白后不能为空。
- `metadata` 只承载通用调用元数据，不放未确认健康事实。
- 本阶段不恢复长期会话，不持久化 session。

### 5.2 AgentRunStatus

至少支持：

```text
COMPLETED
MODEL_ERROR
TOOL_ERROR
LIMIT_REACHED
INVALID_RESPONSE
```

本阶段不加入：

```text
PENDING_CONFIRMATION
PUBLISHED
PLAN_APPROVED
```

### 5.3 AgentRunResult

建议最小合同：

```python
@dataclass(frozen=True)
class AgentRunResult:
    status: AgentRunStatus
    final_text: str | None
    messages: tuple[ModelMessage, ...]
    model_turns: int
    tool_calls: int
    finish_reason: str | None
    trace: RunTrace
    error_code: str | None = None
```

要求：

- 对外结果不依赖 Planning Schema。
- `messages` 可用于确定性测试，但日志不得默认完整输出。
- `trace` 只记录摘要、计数、耗时、错误分类和工具名称。

## 6. Runtime Environment

通用上下文只保留一个日期和时区真相源：

```text
runtimeEnvironment.currentDate
runtimeEnvironment.currentDateTime
runtimeEnvironment.timezone
runtimeEnvironment.locale
```

要求：

- 使用标准库生成 ISO 8601 时间。
- 默认使用当前进程本地时区。
- 支持注入固定时间进行测试。
- 通用 Context 不再暴露独立 `today` 字段。
- `INITIAL_PLANNING` 如仍需要 `today`，由兼容适配器从 `runtimeEnvironment.currentDate` 派生。

## 7. ModelMessage 与 Tool Call 表达

### 7.1 ModelMessage

必须支持角色：

```text
system
user
assistant
tool
```

建议合同：

```python
@dataclass(frozen=True)
class ModelMessage:
    role: ModelRole
    content: str | None
    tool_calls: tuple[ModelToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None
```

约束：

- assistant 消息可同时包含 content 与 tool_calls。
- tool 消息必须包含 `tool_call_id`。
- user/system 消息不得携带 tool_calls。
- Tool Result 必须使用 role=tool，不得伪装成 user 消息。

### 7.2 ModelToolCall

应保留：

```text
id
name
raw_arguments
arguments
```

其中：

- `raw_arguments` 是 Provider 收到的原始 JSON 字符串。
- `arguments` 是成功解析后的只读 Mapping。
- 非法 JSON 由 Provider 抛出明确协议错误，不进入 handler。

### 7.3 Provider 请求顺序

单次工具调用后的消息顺序必须是：

```text
system
user
assistant(tool_calls)
tool(tool_call_id=...)
assistant(final content)
```

同一 assistant 回合存在多个 Tool Call 时：

```text
assistant(tool_call_1, tool_call_2)
tool(result_1)
tool(result_2)
assistant(final)
```

所有 Tool Result 追加完成后才进入下一次模型调用。

## 8. Tool Contract

应复用并收口现有产品 Tool Contract，不创建第二套重复定义。

建议最终合同：

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any] | None
    permission: ToolPermission
    side_effect: ToolSideEffect
    timeout_seconds: float
    handler: ToolHandler
```

### 8.1 本阶段权限

仅允许：

```text
READ_ONLY
```

如果现有枚举名是 `READ`，可继续使用，但语义必须是无持久化副作用的查询或纯计算。

以下权限不得注册到 Phase 2A 产品 Registry：

```text
WRITE
LOW_RISK_WRITE
CONFIRMATION_REQUIRED
PROPOSAL
PUBLISH
FORBIDDEN
```

### 8.2 Tool Schema

模型可见部分只包含：

```text
name
description
input JSON Schema
```

不得暴露：

```text
handler
Python path
内部类名
审计实现
密钥或配置
```

## 9. ToolExecutionResult 与错误策略

建议合同：

```python
@dataclass(frozen=True)
class ToolExecutionResult:
    tool_call_id: str
    tool_name: str
    success: bool
    content: str
    error_code: str | None = None
```

`content` 必须是合法 JSON 字符串。

### 9.1 可返回模型的工具错误

```text
unknown_tool
invalid_arguments
tool_execution_failed
invalid_tool_result
```

错误内容示例：

```json
{
  "success": false,
  "error": {
    "code": "invalid_arguments",
    "message": "value must be a number"
  }
}
```

要求：

- 不包含 traceback、文件路径或内部对象 repr。
- 模型可根据结构化错误决定是否修正并重新调用。
- Runtime 不自动重试失败工具。

### 9.2 不返回模型的错误

Provider 网络、鉴权、超时、限流和响应协议错误直接结束运行：

```text
status=MODEL_ERROR
```

Tool Call 次数或模型回合达到上限：

```text
status=LIMIT_REACHED
```

模型返回 `content=None` 且 `tool_calls=()`：

```text
status=INVALID_RESPONSE
```

## 10. Agent Loop 算法

参考实现流程：

```python
messages = build_initial_messages(request, runtime_environment)
tool_definitions = registry.to_model_definitions()

for model_turn in range(limits.max_model_turns):
    enforce_elapsed_timeout()

    response = provider.complete_turn(
        messages=messages,
        tools=tool_definitions,
        options=options,
    )

    messages.append(assistant_message_from(response))

    if not response.tool_calls:
        if not response.content or not response.content.strip():
            return invalid_response(...)
        return completed(...)

    for tool_call in response.tool_calls:
        if tool_call_count >= limits.max_tool_calls:
            return limit_reached("max_tool_calls", ...)

        tool_result = executor.execute(tool_call)
        messages.append(tool_message_from(tool_result))
        tool_call_count += 1

return limit_reached("max_model_turns", ...)
```

必须满足：

1. 无 Tool Call 时立即完成。
2. 同一回合多个 Tool Call 顺序执行。
3. 本阶段不并行执行。
4. 不丢弃任何已返回 Tool Call。
5. 不自动重试 Provider。
6. 不自动重新执行失败 Tool。
7. 不允许无限循环。
8. 不把 Tool Error 转换成 Python 异常堆栈发给模型。

## 11. 运行限制

建议默认值：

```python
@dataclass(frozen=True)
class LoopLimits:
    max_model_turns: int = 6
    max_tool_calls: int = 8
    timeout_seconds: float = 60
```

校验：

```text
max_model_turns > 0
max_tool_calls >= 0
timeout_seconds > 0
```

本阶段使用同步执行和整体 elapsed time 检查，不引入 asyncio、任务队列或后台 worker。

## 12. 内置只读工具：convert_weight_unit

建议位置：

```text
health_agent/agent/tools/builtin/convert_weight.py
```

输入：

```json
{
  "value": 190,
  "fromUnit": "jin",
  "toUnit": "kg"
}
```

支持单位：

```text
kg
lb
jin
```

确定性换算：

```text
1 jin = 0.5 kg
1 lb = 0.45359237 kg
```

输出：

```json
{
  "value": 190,
  "fromUnit": "jin",
  "convertedValue": 95,
  "toUnit": "kg"
}
```

实现约束：

- 使用 `Decimal` 或等价可靠方式。
- `value` 必须是有限正数。
- 不使用 `eval()`。
- 不做 BMI 分类或医学判断。
- 不生成训练、减脂或饮食建议。
- 这是正式产品只读工具，不是 Mock、Fake 或 Smoke Tool。
- Bootstrap 必须注册此工具。

## 13. 通用系统提示词

建议位置：

```text
health_agent/prompts/agent_system.zh-CN.md
```

最小原则：

```text
根据用户任务决定直接回答或调用可用工具。
工具可以提供确定性结果时优先使用工具。
不得声称执行了未调用的工具。
不得篡改工具结果。
信息不足时明确说明。
当前只允许使用只读工具。
```

禁止加入：

- Program → Phase → WeeklyPlan 固定结构。
- Planner/Reviewer/Publisher 固定流水线。
- 每次必须调用工具。
- 每次必须请求确认。
- 固定疾病、风险或训练动作假设。

## 14. 兼容层隔离

目标关系：

```text
通用 AgentLoop
  └── 默认产品入口

InitialPlanningSkill
  └── legacy compatibility adapter
```

要求：

- 普通用户请求不再通过 trigger 自动进入 `INITIAL_PLANNING`。
- `INITIAL_PLANNING` 可保留显式兼容方法，例如 `run_initial_planning_compat(...)`。
- 通用 Runtime 不导入 PlanningOutput、Program、Phase 或 WeeklyPlan。
- 兼容层不得反向控制通用 Agent Loop。

## 15. 产品入口

### 15.1 agent.main

默认示例请求：

```text
190 斤是多少公斤？请使用可用工具计算。
```

预期：

```text
真实 LLM 返回 convert_weight_unit Tool Call
→ ToolExecutor 得到约 95 kg
→ Tool Result 返回模型
→ 模型输出自然语言结果
```

不得输出固定 Planning JSON。

### 15.2 agent_console.py

改为通用交互入口：

```text
用户输入
→ AgentLoop
→ 真实 LLM
→ 可选 Tool Call
→ 最终自然语言答案
```

不要新增 smoke 脚本。

## 16. 文件级实施建议

实施前必须先检查现有文件，不按名称盲目重建第二套结构。

建议关注：

```text
health_agent/agent/models/base.py
  扩展 ModelMessage 对 assistant/tool 的表达。

health_agent/agent/models/openai_compatible.py
  支持发送 assistant tool_calls 和 role=tool 消息。

health_agent/agent/runtime/loop.py
  替换 single-shot skill runner 或新增清晰隔离的通用 loop。

health_agent/agent/runtime/core.py
  让通用请求进入 AgentLoop；兼容入口显式隔离。

health_agent/agent/runtime/context.py
  统一 runtimeEnvironment，去除通用 today 重复字段。

health_agent/agent/tools/contract.py
  收口单一 ToolDefinition/权限/副作用合同。

health_agent/agent/tools/registry.py
  白名单注册、查找、重复检测、模型 Schema 输出。

health_agent/agent/tools/executor.py
  删除 skeleton/mock/noop 风险处理，执行真实只读 handler。

health_agent/agent/tools/builtin/convert_weight.py
  新增正式只读换算工具。

health_agent/agent/bootstrap.py
  注册产品 ToolRegistry、ToolExecutor、AgentLoop。

health_agent/agent/main.py
health_agent/scripts/agent_console.py
  切换为通用入口。

health_agent/tests/support/scripted_model_provider.py
  仅测试使用，支持按顺序返回多个 ModelResponse。
```

## 17. 推荐实施顺序

1. 先扩展 `ModelMessage` 和 Provider 消息转换测试。
2. 收口 Tool Contract，完成 Registry 与 Executor 确定性测试。
3. 实现 `convert_weight_unit` 及其单元测试。
4. 实现通用 AgentLoop 的直接回答路径。
5. 实现单 Tool Call → Tool Result → 第二轮模型路径。
6. 实现同回合多个 Tool Call。
7. 实现未知工具、参数错误、handler 异常和无效结果。
8. 实现模型回合、工具次数和整体超时限制。
9. 隔离 `INITIAL_PLANNING` 兼容入口。
10. 更新 Bootstrap、main 和 console。
11. 运行全部确定性测试。
12. 最后执行真实 LLM Tool Call 验收。

不要一开始同时重写 Core、Loop、Skill、Safety 和 Session。

## 18. 确定性测试矩阵

| 场景 | Provider 脚本 | 预期 |
|---|---|---|
| 直接回答 | 第一轮 content | `COMPLETED`，0 次工具 |
| 单工具 | Tool Call → final content | 2 次模型回合，1 次工具 |
| 多工具 | 同回合两个 Tool Call → final | 两个结果均追加后进入下一轮 |
| 未知工具 | 未注册 name → final | 返回 `unknown_tool` Tool Result，不执行任意代码 |
| 参数非法 | `value="abc"` | `invalid_arguments`，handler 不执行 |
| Tool 异常 | handler 抛异常 | `tool_execution_failed`，无 traceback 泄漏 |
| Tool 结果非法 | handler 返回不可序列化值 | `invalid_tool_result` |
| 空响应 | content=None 且无 Tool Call | `INVALID_RESPONSE` |
| 最大模型回合 | 持续返回 Tool Call | `LIMIT_REACHED` |
| 最大工具次数 | 超过上限 | `LIMIT_REACHED`，多余工具不执行 |
| 消息顺序 | Tool Call 链路 | system → user → assistant(tool) → tool → assistant(final) |
| 日期来源 | 固定时间 | 通用 Context 只含 runtimeEnvironment 日期字段 |

测试替身必须只位于 `health_agent/tests/support/`，不得被产品 Bootstrap 引用。

## 19. 真实 LLM 验收

前提：本地 `health_agent/.env` 已配置真实模型。

执行：

```bash
cd health_agent
python3 -m agent.main
```

测试输入：

```text
190 斤是多少公斤？请调用可用的重量转换工具，不要自行心算。
```

验收标准：

1. 真实模型返回原生 Tool Call。
2. Tool 名称为 `convert_weight_unit`。
3. ToolExecutor 真实执行并得到约 95 kg。
4. Tool Result 使用 role=tool 返回真实模型。
5. 模型返回最终自然语言答案。
6. 模型调用至少两轮。
7. 工具调用至少一次。
8. 不经过 `INITIAL_PLANNING`。
9. 不出现 Mock、Fake 或 Smoke 产品路径。
10. 不打印 API Key、完整 prompt 或 raw response。

如果模型不支持原生 Tool Call，归类为：

```text
MODEL_TOOL_CALL_UNSUPPORTED
```

不得解析普通文本中的伪函数调用绕过限制。

## 20. 验证命令

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests -v

git diff --check
```

产品路径测试替身检查：

```bash
rg "MockProvider|ScriptedModelProvider" \
  health_agent/agent \
  health_agent/scripts
```

结果必须为空。

任意代码执行能力检查：

```bash
rg "eval\\(|exec\\(|subprocess|os\\.system" \
  health_agent/agent/tools \
  health_agent/agent/runtime
```

不得出现 shell 或任意代码执行能力。

## 21. Definition of Done

Phase 2A 只有同时满足以下条件才可标记为完成：

- 通用入口不再依赖 `INITIAL_PLANNING`。
- 直接回答、单 Tool Call、多 Tool Call、错误和限制路径均有确定性测试。
- `convert_weight_unit` 是真实产品工具并由 Bootstrap 注册。
- Tool Result 以原生 role=tool 消息返回模型。
- 普通测试无网络、无真实密钥依赖。
- 真实 LLM 至少成功完成一次两轮 Tool Call 链路。
- 产品代码中不存在 Mock、Fake 或 Smoke Provider/Tool。
- 未修改禁止目录。
- README 与 `mvp-exec-plan.md` 只在真实验收后更新为完成状态。

## 22. 完成报告模板

```text
修改文件：
新增文件：
删除文件：

通用 Agent Loop 调用链：
ModelMessage 的 Tool Call/Tool Result 表达：
Tool Contract：
ToolRegistry 职责：
ToolExecutor 职责：
最大模型回合数：
最大工具调用数：
Tool Error 策略：
convert_weight_unit 实际结果：

确定性测试：
真实 LLM Tool Call：
实际模型调用轮数：
实际工具调用次数：
是否经过 INITIAL_PLANNING：
产品路径是否出现 Mock/Fake/Smoke：
是否触碰禁止范围：
尚未完成事项：
```

完成后停止，不进入 Safety Guard、写操作 Tool、Confirmation、数据库、Memory、Plan Publish、多 Agent 或 Subagent。
