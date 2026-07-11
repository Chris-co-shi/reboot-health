# MVP 执行计划

本文档是当前里程碑、状态、验收结果和下一步的唯一事实来源。

历史 Java/Flutter 多运行时里程碑不再作为当前开发路线；相关代码和 ADR 仍保留为 legacy 与迁移参考。

## 1. 状态约定

| 状态 | 含义 |
|---|---|
| `DONE` | 自动化验证和要求的真实运行验收均完成 |
| `DONE_EXPLICIT` | 自动化验收完成，但能力需要显式启用或显式调用，尚非默认产品流程 |
| `READY` | 设计、范围和验收标准已确认，可以开始实现 |
| `IN_PROGRESS` | 正在实施，尚未完成全部验收 |
| `IMPLEMENTED_WITH_BLOCKERS` | 主体代码存在，但真实环境或关键验收仍被阻塞 |
| `TODO` | 尚未进入实施 |
| `BLOCKED` | 存在必须先解决的依赖或决策 |

不得把仅存在代码、只通过 Mock、只通过静态分析或未运行真实链路的能力标记为 `DONE`。

## 2. 当前总状态

```text
当前架构：Python-first 模块化单体
当前真实目录：health_agent/
当前已完成：Phase 1、1.1、1.2、1.3、Phase 2A、Phase 2B Runtime 持久化安全 Slice
当前待实施：Phase 2B 只读健康上下文工具、Console/API 确认入口、产品级 Safety
下一步：先确定只读健康上下文的数据来源与 Repository Port，或将显式 Runtime Store 接入后续 CLI/API
```

当前产品链路是：

```text
用户输入
→ 产品 Bootstrap
→ GenericAgentLoop
→ 真实 LLM
→ 可选只读 Tool Call
→ ToolExecutor
→ role=tool Result
→ 真实 LLM
→ 最终自然语言回答
```

## 3. 已完成阶段

### Phase 1：真实 Provider 与通用 Model Contract

状态：`DONE`

完成内容：

- 当前 Python 主目录统一为 `health_agent/`。
- 产品运行不再默认使用 MockProvider。
- Provider 合同迁移为通用 `complete_turn(...)`。
- OpenAI-compatible Provider 支持普通文本、Tool Call、usage 和 finish reason 解析。
- 产品 Bootstrap 显式注入真实 Provider。
- 测试 Scripted Provider 仅位于 `tests/`。
- 删除旧业务 Mock、Smoke 和 Eval 主路径。

验收：

- compileall 通过。
- unittest 通过。
- 缺配置时明确失败，不回退 Mock。

### Phase 1.1：LLM 配置入口收口

状态：`DONE`

完成内容：

- 环境变量统一为 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`。
- 规范 `.env` 路径为 `health_agent/.env`。
- shell 环境变量优先于 `.env`。
- `LLMSettings` 为唯一 LLM 配置对象。
- Provider 不读取环境变量，不加载 `.env`。
- `RUN_LLM_INTEGRATION` 显式控制真实集成测试。

验收：

- `.env` 被 Git ignore。
- API Key 不进入 repr、日志或异常。
- 默认测试不访问网络。

### Phase 1.2：真实 LLM 接入验收

状态：`DONE`

完成内容：

- 真实 Provider 网络请求成功。
- `agent.main` 经 Bootstrap 调用真实 LLM。
- Provider 返回合法 `ModelResponse`。
- 真实响应成功进入 `INITIAL_PLANNING` 兼容解析。
- 进程 exit code 为 0。

### Phase 1.3：INITIAL_PLANNING 兼容层去污染

状态：`DONE`

完成内容：

- 删除 Python 主路径中的 Java/Domain Kernel 职责文案。
- 删除未经用户输入确认的颈椎、血压、游泳等固定健康注入。
- 删除业务型 TodayAction fallback。
- `questions` 改为结构化对象数组。
- Runtime 提供 currentDate/currentDateTime/timezone/locale。
- 信息不足可返回 `insufficient_information` 与空草案。

验收：

- 确定性测试通过。
- 真实 LLM 返回 `insufficient_information` 空草案。
- 未询问今天日期。
- 未出现未经确认的健康限制。
- 未出现 Java 文案。

## 4. 当前阶段

### Phase 2A：通用只读 Tool Call Agent Loop

状态：`DONE`

权威实施规范：

[`implementation/phase-2a-read-only-tool-call-loop.md`](implementation/phase-2a-read-only-tool-call-loop.md)

#### 目标

建立真实、有限轮次、非固定工作流的 Agent Loop：

```text
用户输入
→ Model Turn
→ Tool Call
→ 只读 Tool 执行
→ role=tool Result
→ Model Turn
→ Final content
```

#### 范围

- 通用 `AgentRequest` 与 `AgentRunResult`。
- system/user/assistant/tool 消息合同。
- assistant Tool Call 和 tool_call_id 关联。
- ToolRegistry 白名单注册与模型 Schema 输出。
- ToolExecutor 真实只读执行。
- Tool Error 结构化返回模型。
- 最大模型回合、最大工具次数和整体超时。
- 正式产品工具 `convert_weight_unit`。
- 通用 `agent.main` 与 `agent_console.py`。
- `INITIAL_PLANNING` 隔离为显式 legacy 兼容入口。

#### 不包含

- 写操作 Tool。
- Safety Guard。
- Confirmation Pause/Resume。
- 数据库、Repository 或 Memory。
- Plan Publish、DailyRecord。
- FastAPI。
- 多 Agent、Subagent、DAG 或工作流引擎。
- Java、Flutter、Vue 或 Compose 改造。

#### 自动化验收

必须覆盖：

- 直接回答。
- 单 Tool Call。
- 同回合多个 Tool Call。
- 未知工具。
- 参数非法。
- handler 异常。
- Tool 结果非法。
- 空模型响应。
- 最大模型回合。
- 最大工具次数。
- system → user → assistant(tool) → tool → assistant(final) 消息顺序。
- Runtime Environment 日期唯一来源。

执行：

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests -v
git diff --check
```

#### 真实 LLM 验收

输入：

```text
190 斤是多少公斤？请调用可用的重量转换工具，不要自行心算。
```

必须确认：

- 模型返回原生 `convert_weight_unit` Tool Call。
- ToolExecutor 得到约 95 kg。
- Tool Result 以 role=tool 返回模型。
- 模型返回最终自然语言答案。
- 至少 2 次模型回合、至少 1 次工具调用。
- 不经过 `INITIAL_PLANNING`。
- 产品路径无 Mock、Fake 或 Smoke。

#### 完成条件

已完成自动化测试和真实 LLM Tool Call 验收。

验收摘要：

```text
确定性测试：145 个，全部通过，默认跳过 2 个显式真实集成测试
真实模型调用轮数：2
真实工具调用次数：1
真实工具名称：convert_weight_unit
真实转换结果：190 jin → 95 kg
真实入口不经过 INITIAL_PLANNING
```

已确认：

- `agent.main` 和 `scripts/agent_console.py` 默认进入通用 `GenericAgentLoop`。
- 产品 Bootstrap 注册正式只读 `convert_weight_unit` Tool。
- Tool Result 使用 `role=tool` 返回模型。
- 产品路径无 Mock/Fake/Smoke。
- 未记录 API Key、Base URL、完整 Prompt 或完整模型响应。

### Phase 2B Runtime 持久化安全 Slice

状态：`DONE_EXPLICIT`

说明：这一组 Slice 完成的是 Agent Runtime 在确认、恢复和本地 JSON 持久化下的安全基础；
它不等同于只读健康上下文工具已经完成，也不表示默认产品入口已经启用磁盘持久化。

完成内容：

- `AgentSession` 支持 RUNNING ownership、`active_run_id`、`run_fence_generation`、
  heartbeat 和 lease。
- `GenericAgentLoop` 在运行开始、heartbeat、checkpoint 和 finalization 时执行 fence
  校验，旧 owner 失去 ownership 后不得继续写入。
- JSON Session Store schema 支持 lease 与 execution checkpoint，并保留 v1/v2 安全迁移。
- `RunExecutionCheckpoint` 记录 `DRIVE_READY`、`MODEL_CALL_IN_FLIGHT`、
  `TOOL_CALL_IN_FLIGHT` 和 `FINALIZING`。
- stale recovery 只自动恢复 `DRIVE_READY`；模型调用中、工具调用中和最终收敛中的不确定状态
  fail-closed，不自动重试或覆盖。
- PendingAction Store 支持显式维护扫描、CAS 过期未引用 `PENDING`、CAS 删除超过 retention 的
  未引用终态 Action。

不包含：

- 后台 worker 或定时清理。
- Console/API 的确认、拒绝、恢复命令。
- 正式写操作 Tool。
- SQLite、Redis、FastAPI 或消息队列。
- 产品级 Safety Guard、Memory 或多 Agent。

自动化验收：

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_json_store_multiprocess -v
python3 -m unittest tests.test_run_lease_multiprocess -v
python3 -m unittest tests.test_stale_recovery -v
python3 -m unittest tests.test_orphan_pending_actions -v
git diff --check
```

## 5. 后续阶段

### Phase 2B 后续：只读健康上下文工具

状态：`TODO`

候选范围：

- `get_user_profile`
- `get_current_plan`
- `get_recent_daily_records`
- `get_training_history`
- `get_execution_summary`

前提：先确定内存/Repository Port 与数据来源；不得在 Runtime 中硬编码用户健康事实。

### Phase 2C：Session、Events 与 Persistence

状态：`TODO`

范围：

- 将显式 JSON Runtime Store 或后续确认的持久化方案接入产品 CLI/API。
- Session/Event 模型与产品审计摘要。
- AgentRun 与 ToolCall 审计摘要。
- 运行恢复所需的最小状态。

### Phase 3：强制 Safety Guard

状态：`TODO`

范围：

- Input Guard。
- Pre-Tool Guard。
- Pre-Publish Guard。
- Pre-Output Guard。
- 确定性 BLOCK/WARN 决策。

Safety 不得仅实现成模型可选 Tool。

### Phase 4：Proposal、Confirmation 与 Publish

状态：`TODO`

范围：

- Proposal Tool。
- Runtime `PENDING_CONFIRMATION` 暂停协议。
- 确认关联、内容哈希、revision 与幂等。
- 发布前 Safety Guard。
- PlanVersion 与快照语义迁移。

`request_user_confirmation` 不作为普通 Tool。

### Phase 5：档案、记录和训练领域迁移

状态：`TODO`

范围：

- UserProfile。
- Health Facts/Constraints。
- Daily Records。
- Training Records。
- Plan/PlanVersion。
- Repository Ports 与 Persistence Adapters。
- 旧 Java 领域不变量迁移。

### Phase 6：产品 API 与客户端

状态：`TODO`

范围：

- FastAPI 产品入口。
- API 鉴权与隐私边界。
- 正式客户端选择与迁移。
- legacy Java/Flutter/Compose 下线计划。

## 6. Legacy 说明

旧文档曾记录以下路线：

```text
Flutter → Java AgentRun → Python Runtime
```

该路线已由 ADR 0010 替代，不再是当前实施目标。

历史代码可以用于迁移业务语义，但不得因为旧实现存在而声称当前 Python 产品已经具备：

- Plan 发布。
- 数据库存储。
- Safety Guard。
- Confirmation Resume。
- 正式客户端端到端链路。

## 7. OPEN

- Phase 2C 的本地持久化最终选择 SQLite 还是其它方案。
- Python 模块化单体中旧 PlanVersion、revision、幂等和审计语义的迁移顺序。
- 正式客户端继续使用 Flutter、改为 Web，还是先以 API/CLI 完成闭环。
- 医疗与运动安全阈值的专业依据与审核流程。
