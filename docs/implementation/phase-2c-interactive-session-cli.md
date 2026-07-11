# Phase 2C：Interactive Session CLI 实施规范

## 1. 状态

`READY`

本规范定义当前下一阶段的唯一工程交接目标：在不引入健康领域数据、数据库、Safety Guard 或正式写操作的前提下，将现有 GenericAgentLoop 和 JSON Runtime Store 组装成可连续对话、可显式恢复的本地交互式 CLI。

当前阶段与完成状态以 [`../mvp-exec-plan.md`](../mvp-exec-plan.md) 为准。

## 2. 背景

当前 `agent.main` 与 `scripts/agent_console.py` 是 one-shot 入口：

```text
一次用户输入
→ GenericAgentLoop
→ 可选 Tool Call
→ 最终回答
→ 进程退出
```

Runtime 已支持：

- `session_id`。
- Message History。
- JSON Session/PendingAction Store。
- ConfirmationCoordinator。
- lease、fence、checkpoint 和 stale recovery。

但默认产品入口每次重新创建内存 Store，用户无法完成：

```text
Agent 提问
→ 用户补充信息
→ Agent 基于上轮内容继续
```

Phase 2C 只补齐产品会话入口和上下文连续性，不扩展健康业务能力。

## 3. 用户目标体验

```bash
cd health_agent
python3 scripts/agent_chat.py
```

示例：

```text
Health Agent started. Session: <id>
You: 帮我设计一套增肌计划，需要什么信息可以问我
Agent: 请先告诉我年龄、性别、身高、体重和健康限制。
You: 男，33 岁，175cm，87kg。
Agent: 已了解。你每周能训练几天，家里有哪些器械？
You: 每周五天，有哑铃和弹力带。
Agent: ...
```

JSON 模式：

```bash
python3 scripts/agent_chat.py \
  --storage json \
  --storage-directory runtime-state \
  --session-id chris-main
```

退出后使用相同参数重新启动，应恢复此前 Session 消息。

## 4. 任务合同

```text
Primary Module:
  health_agent 交互式 Session CLI 与现有 Runtime Store 组装

Allowed Paths:
  health_agent/scripts/agent_chat.py
  health_agent/agent/bootstrap.py
  health_agent/agent/main.py（仅共享展示/错误辅助函数的最小调整）
  health_agent/agent/runtime/（仅修复 Phase 2C 验收暴露的通用 Session 问题）
  health_agent/tests/
  health_agent/README.md
  README.md
  docs/mvp-exec-plan.md
  docs/architecture.md
  docs/implementation/phase-2c-interactive-session-cli.md
  AGENTS.md
  health_agent/AGENTS.md

Forbidden Paths:
  backend/
  clients/flutter/
  frontend/
  deploy/

Out of Scope:
  FastAPI
  SQLite/PostgreSQL/Redis
  健康领域 Repository
  UserProfile/HealthConstraint/Plan 持久化
  长期 Memory 自动提取
  Safety Guard
  正式写操作 Tool
  Plan Publish
  多 Agent/Sub-Agent/DAG
  后台 worker
```

## 5. 设计边界

### 5.1 复用现有 Runtime Components

交互式 CLI 必须只创建一次：

```python
components = create_generic_runtime_components_from_env(...)
```

随后在输入循环中复用：

- `components.loop`。
- `components.session_store`。
- `components.pending_action_store`。
- `components.confirmation_coordinator`。

不得每轮输入重新创建 Bootstrap 或 Store。

### 5.2 固定当前 session_id

每个交互式 CLI 实例维护一个当前 `session_id`。

每轮调用：

```python
components.loop.run(
    AgentRequest(
        user_text=user_text,
        session_id=current_session_id,
    )
)
```

`/new` 生成新的不透明 Session ID，并切换当前会话；旧会话不得被覆盖。

### 5.3 Clarification 不是 Confirmation

Agent 的普通追问，例如：

```text
你的年龄是多少？
家里有哪些器械？
```

只通过下一轮 user message 继续，不创建 PendingAction，不进入 WAITING_CONFIRMATION。

PendingAction 只用于未来高影响 Tool 或写入审批。

### 5.4 Storage 模式

支持：

```text
memory
json
```

默认建议：

- 未显式配置时使用 `memory`，保持安全和当前行为。
- `json` 必须要求 `--storage-directory`。
- JSON Store 仅用于受控本地环境；CLI 启动时应提示其为明文存储。

不得在本阶段从环境变量隐式启用磁盘持久化。

### 5.5 输出边界

交互式 CLI 默认向用户展示：

- `final_text`。
- 必要的稳定错误信息。
- Session ID 和状态摘要。

不默认展示：

- 完整 Message History。
- PendingAction arguments。
- raw model response。
- API Key、Base URL 或认证信息。
- Python traceback。

## 6. CLI 命令

首版必须支持：

| 命令 | 行为 |
|---|---|
| `/help` | 显示命令和当前存储模式 |
| `/new` | 创建并切换到新 Session |
| `/status` | 显示当前 Session ID、状态、消息数量和存储模式 |
| `/resume <session-id>` | 切换到已存在 Session；不存在时明确失败 |
| `/exit` | 正常退出 |

可选：

- `/sessions`：列出 Session；仅在现有 Store Port 能安全支持时进入首版。
- `/delete <session-id>`：需要独立生命周期和安全语义，不得为了方便直接删除文件。

普通用户输入不得与命令解析混淆。未知 `/command` 应提示帮助，不发送给模型。

## 7. Session 状态处理

### ACTIVE / COMPLETED

允许追加新的用户消息并开始下一次 Run。

### RUNNING

- lease 未过期：返回 Session 已在运行。
- lease 已过期：提示需要 stale recovery，不自动绕过。

### WAITING_CONFIRMATION

当前 Phase 2C 没有正式写 Tool，但 CLI 必须安全展示“等待确认”的状态，不得把普通用户文本作为隐式 approve。

### FAILED

不得静默重置。用户可 `/new`，或后续通过明确恢复命令处理。

## 8. 上下文预算

Phase 2C 首版允许继续使用完整 Session Message History，但必须：

- 在文档中声明长期消息增长风险。
- 为后续 Conversation Summary 保留独立字段/Port 边界，不把摘要伪装成 user/system 原始事实。
- 不在本阶段自动生成或持久化健康领域 Memory。

如果真实模型上下文限制阻塞验收，可新增最小 Conversation Summary 机制，但必须单独记录：

- 摘要覆盖的消息范围。
- 摘要生成来源和时间。
- 原始消息是否仍保留。
- 摘要不得成为已确认健康事实。

## 9. 错误处理

必须稳定处理：

- 缺少 LLM 配置。
- Provider 网络/鉴权/限流/超时错误。
- Session 不存在。
- JSON 目录不可创建或不可写。
- Session version conflict。
- Session 已在运行。
- stale Session 需要恢复。
- 用户输入为空。
- EOF / Ctrl-D / Ctrl-C。

CLI 不得输出敏感 traceback；调试日志仍遵守现有脱敏规则。

## 10. 测试矩阵

### 10.1 确定性测试

必须覆盖：

- 启动时创建当前 Session ID。
- 两次用户输入使用同一个 Session ID。
- 第二次模型调用消息中包含第一轮 user/assistant 消息。
- `/new` 切换新 Session，消息历史隔离。
- `/resume` 恢复已存在 Session。
- `/resume` 不存在 Session 时不调用模型。
- memory 模式不写磁盘。
- json 模式重建 Runtime Components 后可读取旧 Session。
- 未知命令不发送给模型。
- `/exit` 正常退出。
- 配置错误和 Store 错误不泄露敏感信息。

### 10.2 回归测试

必须确认：

- `agent.main` 仍可 one-shot 运行。
- `agent_console.py` 仍要求 `--user-text`。
- `convert_weight_unit` 真实 Tool Call 链路不受影响。
- 现有 lease、checkpoint、stale recovery 和 orphan 测试继续通过。

### 10.3 真实 LLM 验收

使用真实 Provider 完成：

```text
用户：帮我设计一套增肌计划，需要什么信息可以问我
Agent：提出基础信息问题
用户：有训练过，断断续续。每周五天，基本在家，体脂率 30%。
```

必须确认第二轮回答：

- 能识别第一轮目标是“增肌计划”。
- 不重新询问用户想做什么。
- 能基于已提供信息继续询问缺失的关键事实。
- 不声称已经读取不存在的健康档案或历史训练记录。

JSON 模式还必须：

- 退出进程。
- 使用相同 Session ID 重新启动。
- 输入“继续刚才的话题”。
- 模型能看到此前消息历史。

## 11. 验证命令

```bash
cd health_agent
python3 -m compileall agent tests scripts
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_json_store_multiprocess -v
python3 -m unittest tests.test_run_lease_multiprocess -v
python3 -m unittest tests.test_stale_recovery -v
python3 -m unittest tests.test_orphan_pending_actions -v

git diff --check
```

真实模型验收必须显式执行并记录模型回合数、工具调用数、Session ID 是否一致以及是否跨进程恢复。

## 12. 完成定义

Phase 2C 标记为 `DONE` 前必须满足：

- 用户可通过交互式 CLI 连续输入至少两轮。
- 同一 Session 的历史真实进入下一次模型调用。
- JSON 模式可跨进程恢复。
- one-shot 入口不回归。
- 普通 Clarification 未被建模成 Confirmation。
- 未引入健康领域事实、数据库或长期 Memory 半成品。
- 文档和真实运行体验一致。
