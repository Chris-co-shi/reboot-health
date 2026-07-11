# Python Health Agent Runtime

`health_agent/` 是 reboot-health 当前与目标 Python Runtime。产品运行入口直接使用 OpenAI-compatible Chat Completions Provider，不会在配置缺失时回退测试替身。

## 当前状态

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A 通用只读 Tool Call Agent Loop：DONE
Phase 2B Runtime 状态、确认、恢复与 JSON 持久化安全基础：DONE_EXPLICIT
Phase 2C Interactive Session & Conversation Context：DONE
```

当前 Phase 2C 工程交接规范：

[`../docs/implementation/phase-2c-interactive-session-cli.md`](../docs/implementation/phase-2c-interactive-session-cli.md)

已完成 Phase 2A 验收参考：

[`../docs/implementation/phase-2a-read-only-tool-call-loop.md`](../docs/implementation/phase-2a-read-only-tool-call-loop.md)

## 当前用户体验

当前保留 one-shot CLI，并新增 interactive Session CLI。

one-shot CLI：

```text
一次用户输入
→ 产品 Bootstrap
→ GenericAgentLoop
→ OpenAI-compatible Chat Completions
→ Assistant content 或原生 Tool Call
→ ToolRegistry / ToolExecutor
→ role=tool Result
→ 下一轮真实模型
→ 最终自然语言回答
→ 进程退出
```

interactive CLI：

```text
启动 scripts/agent_chat.py
→ 单进程复用同一组 Runtime Components
→ 同一个 session_id 连续追加 user/assistant/tool 消息
→ 显式 JSON 模式可在进程退出后恢复同一 Session
```

这意味着：

- 单次 Run 内支持模型与工具多回合。
- 每个 `agent_console.py --user-text` 命令默认是新的进程和新的内存 Store。
- Agent 可以在 one-shot 答案中提出问题，但 one-shot console 不会继续读取下一轮用户输入。
- `agent_chat.py` 可以连续读取用户输入，普通澄清问题通过下一轮 user message 继续。
- `agent_chat.py` 默认使用 memory Store；JSON Store 必须显式传入目录。
- JSON Store 为本地明文，可能包含用户消息、assistant 消息和 Tool Result。

## 目录结构

```text
health_agent/
  agent/
    bootstrap.py     # 产品 Composition Root
    runtime/         # Loop、Session、Confirmation、Lease、Checkpoint、Recovery、Trace
    models/          # ModelProvider 与 OpenAI-compatible Provider
    tools/           # Tool contract、registry、executor 和只读内置工具
    skills/          # INITIAL_PLANNING legacy compatibility
    schemas/         # Agent、Planning、Tool、Memory、Health Schema
    memory/          # MemoryCandidate 骨架，不持久化
    api/             # API 层预留，当前不接 Web 框架
  prompts/           # 通用 Agent system prompt
  scripts/           # one-shot console 与 interactive chat
  tests/             # unittest 和测试专用 scripted provider
```

测试替身只允许存在于 `tests/`，产品 Bootstrap 不引用测试目录。

## 当前能力状态

| 能力 | 状态 | 说明 |
|---|---|---|
| OpenAI-compatible Provider | `DONE` | 支持普通文本、Tool Call、usage 和 metadata 解析 |
| 产品 Bootstrap | `DONE` | 组装真实 Provider、ToolRegistry、ToolExecutor 和 GenericAgentLoop |
| INITIAL_PLANNING | `LEGACY_COMPAT` | 仅显式兼容入口，不是默认产品路径 |
| ModelMessage Tool 消息 | `DONE` | assistant tool_calls、role=tool、tool_call_id 完整往返 |
| ToolRegistry / ToolExecutor | `DONE` | 只读白名单、参数校验、确定性执行和结构化错误 |
| convert_weight_unit | `DONE` | kg、lb、jin 确定性换算 |
| Tool Call Agent Loop | `DONE` | 直接回答、单/多 Tool Call、限制与错误收敛 |
| JSON Runtime Store | `DONE_EXPLICIT` | Session/PendingAction 本地 JSON 持久化，默认入口未启用 |
| Confirmation Runtime | `DONE_EXPLICIT` | 底层批准、拒绝和恢复协议，尚无产品 CLI/API 入口 |
| Lease / Fencing | `DONE_EXPLICIT` | RUNNING owner、heartbeat、lease 与 fence generation |
| Checkpoint / Recovery | `DONE_EXPLICIT` | 仅 DRIVE_READY 自动恢复，其余 in-flight 状态 fail-closed |
| Orphan Maintenance | `DONE_EXPLICIT` | 显式扫描、过期和清理 orphan PendingAction |
| Interactive Session CLI | `DONE` | `scripts/agent_chat.py` 支持连续对话、/new、/status、/resume 和显式 JSON 恢复 |
| 健康领域 Repository / Read Tools | `TODO` | 尚不能读取真实档案、计划或训练记录 |
| 完整 Safety / 写操作 / API | `TODO` | 后续独立阶段 |

## 配置

产品入口默认读取 `health_agent/.env`。从仓库根目录或 `health_agent/` 目录运行都会解析同一个文件，且 shell 环境变量优先于 `.env`。

```bash
cd health_agent
cp .env.example .env
```

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=60
```

缺少 `LLM_BASE_URL`、`LLM_API_KEY` 或 `LLM_MODEL` 时，Bootstrap 会明确失败。

诊断日志默认不输出完整 Prompt、完整健康原文、完整模型响应或 API Key。

## 当前直接使用

```bash
cd health_agent
python3 -m agent.main --user-text "190 斤是多少公斤？请调用工具计算。"
python3 scripts/agent_console.py --user-text "用简单的话解释渐进超负荷。"
```

输出为安全摘要：

```text
status / modelTurns / toolCalls / finishReason / answer
```

当前 console 不支持：

- 启动后持续输入。
- Agent 提问后等待用户下一轮回答。
- 默认跨进程恢复。
- Session 列表、切换或删除。

## 交互式 Session CLI

默认 memory 模式：

```bash
cd health_agent
python3 scripts/agent_chat.py
```

显式 JSON 模式：

```bash
python3 scripts/agent_chat.py \
  --storage json \
  --storage-directory runtime-state \
  --session-id chris-main
```

参数：

| 参数 | 说明 |
|---|---|
| `--storage memory\|json` | 默认 `memory`；`json` 必须显式提供目录 |
| `--storage-directory <path>` | JSON Store 目录；不会通过环境变量隐式启用 |
| `--session-id <id>` | 指定已有或新 Session；未提供时生成不透明随机 ID |

命令：

| 命令 | 行为 |
|---|---|
| `/help` | 显示命令、当前 storage 和 JSON 明文提醒 |
| `/new` | 生成并切换到新的 Session，不覆盖旧 Session |
| `/status` | 显示 Session ID、状态、消息数量、storage 和是否已持久化 |
| `/resume <session-id>` | 只切换到已存在 Session；不存在时不调用模型 |
| `/exit` | 正常退出 |

空输入不会调用模型；未知 `/command` 只显示帮助，不发送给模型。Phase 2C
不实现 `/delete` 或 Session 列表。

## 本地 JSON Runtime Store

默认产品入口使用 `InMemorySessionStore` 和 `InMemoryPendingActionStore`。

显式启用：

```python
from pathlib import Path
from agent.bootstrap import create_generic_runtime_components_from_env

components = create_generic_runtime_components_from_env(
    storage_mode="json",
    storage_directory=Path("runtime-state"),
)
```

目录布局：

```text
runtime-state/
  sessions/
    <sha256(session_id)>.json
    <sha256(session_id)>.lock
  pending-actions/
    <sha256(action_id)>.json
    <sha256(action_id)>.lock
```

Store 使用 SHA-256 文件键、实体级跨进程锁、CAS 和原子替换。

注意：JSON 文件是本地明文，可能包含用户消息、assistant 消息、Tool Result 和 PendingAction arguments。本能力只适合受控本地环境，不声明医疗数据合规能力。

## Session、Context 与 Memory

项目明确区分：

```text
Session Message History：连续对话技术状态
Runtime Context：当前模型回合输入
Conversation Summary：上下文压缩，不是健康事实
Domain Facts：UserProfile、HealthConstraint、Goal、Plan、Records
Memory Candidate：模型推断候选，确认前不得生效
```

详细决策：

[`../docs/decisions/0011-session-context-memory-boundaries.md`](../docs/decisions/0011-session-context-memory-boundaries.md)

普通澄清问题不创建 PendingAction。PendingAction 只用于未来高影响 Tool、写入或发布审批。

## 运行租约、恢复与 orphan 维护

Runtime 在 RUNNING Session 上持久化 `active_run_id`、`run_fence_generation`、heartbeat、lease 和 execution checkpoint。

恢复策略：

- `DRIVE_READY`：可安全恢复。
- `MODEL_CALL_IN_FLIGHT`：不自动重放。
- `TOOL_CALL_IN_FLIGHT`：不自动重放。
- `FINALIZING`：不自动覆盖。

PendingAction orphan 维护必须显式调用；默认 dry-run 不返回 arguments 或 result content。

## 验证

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

真实 LLM 集成测试必须显式设置 `RUN_LLM_INTEGRATION=1`。

Phase 2A 验收摘要：

```text
确定性测试：145 个通过，默认跳过 2 个真实集成测试
真实模型调用轮数：2
真实工具调用次数：1
真实工具名称：convert_weight_unit
真实转换结果：190 jin → 95 kg
```

Phase 2C 验收摘要：

```text
确定性测试：375 个通过，默认跳过 2 个显式真实集成测试
真实同进程连续对话：2 次 Agent Run，Session ID 一致
真实 JSON 跨进程恢复：2 次 Agent Run，Session ID 一致
真实模型回合数：同进程 1 + 1，JSON 恢复 1 + 1
真实工具调用次数：0
未经过 INITIAL_PLANNING
```

## 开发阅读顺序

```text
../AGENTS.md
→ AGENTS.md
→ ../docs/architecture.md
→ ../docs/mvp-exec-plan.md
→ ../docs/decisions/0011-session-context-memory-boundaries.md
→ ../docs/implementation/phase-2c-interactive-session-cli.md
→ README.md
```

## 边界

- 不做医学诊断，不替代医生意见。
- 不开放 shell、任意文件系统或任意 SQL Tool。
- 不把模型输出写成已保存、已确认、已发布或已生效。
- 不记录完整健康原文、认证信息、API Key、完整 Prompt 或 raw response。
- Phase 2C 不实现健康领域数据库、长期 Memory、Safety Guard、正式写操作、FastAPI 或多 Agent。
