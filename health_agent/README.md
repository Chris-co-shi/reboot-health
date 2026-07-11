# Python Health Agent Runtime

`health_agent/` 是 reboot-health 当前与目标 Python Runtime。产品运行入口直接使用 OpenAI-compatible Chat Completions Provider，不会在配置缺失时回退到测试替身。

当前状态：

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A 通用只读 Tool Call Agent Loop：DONE
Phase 2B Runtime 确认、恢复与 JSON 持久化基础：DONE（显式启用）
```

Agent Runtime 开发前必须读取：

[`../docs/implementation/phase-2a-read-only-tool-call-loop.md`](../docs/implementation/phase-2a-read-only-tool-call-loop.md)

## 当前运行模型

```text
用户输入
→ 产品 Bootstrap
→ GenericAgentLoop
→ OpenAI-compatible Chat Completions
→ Assistant content 或原生 Tool Call
→ ToolRegistry / ToolExecutor
→ role=tool Result
→ 下一轮真实模型
→ 最终自然语言回答
```

`INITIAL_PLANNING` 已完成真实 LLM 验收和去污染，但现在只保留为显式 legacy compatibility 入口；默认 main 和 console 不再进入该路径。

## Phase 2A 目标模型

```text
用户输入
→ 通用 AgentLoop
→ 真实 LLM
→ Assistant content 或原生 Tool Call
→ ToolRegistry / ToolExecutor
→ role=tool Result
→ 真实 LLM
→ 最终自然语言回答
```

Phase 2A 只实现只读或纯计算 Tool，不接数据库、写操作、Safety Guard、Confirmation 或 Memory。

## 目录结构

```text
health_agent/
  agent/
    bootstrap.py     # 产品 Composition Root
    runtime/         # Core、Loop、Session、Context、Trace、State
    models/          # 通用 ModelProvider 合同与 OpenAI-compatible Provider
    tools/           # Tool contract、registry、executor 和内置只读工具
    skills/          # 临时 INITIAL_PLANNING 兼容 Skill
    schemas/         # Agent、Planning、Tool、Memory、Health Schema
    memory/          # MemoryCandidate 骨架，不持久化
    api/             # API 层预留，当前不接 Web 框架
  skills/            # 外置 Prompt 与 Skill metadata
  prompts/           # 公共 Prompt；Phase 2A 将加入通用 Agent system prompt
  scripts/           # 本地 console
  tests/             # unittest 和测试专用 scripted provider
```

测试替身只允许存在于 `tests/`，产品 Bootstrap 不引用测试目录。

## 当前能力状态

| 能力 | 状态 | 说明 |
|---|---|---|
| OpenAI-compatible Provider | `DONE` | 实现 `complete_turn()`，支持普通文本、Tool Call、usage 和 metadata 解析。 |
| 产品 Bootstrap | `DONE` | 加载 `health_agent/.env`，创建真实 Provider、只读 ToolRegistry、ToolExecutor 和 GenericAgentLoop。 |
| INITIAL_PLANNING | `LEGACY_COMPAT` | 真实 LLM 可运行；不再注入固定健康事实；后续显式隔离。 |
| 通用 ModelMessage Tool 消息 | `DONE` | 支持 assistant tool_calls、role=tool、tool_call_id 和完整消息往返。 |
| ToolRegistry / ToolExecutor | `DONE` | 只读白名单注册、模型 Schema 输出、确定性执行和结构化 Tool Result。 |
| convert_weight_unit | `DONE` | 正式只读产品工具，支持 kg、lb、jin 确定性换算。 |
| Tool Call Agent Loop | `DONE` | 支持直接回答、单/多 Tool Call、Tool Error 回送、运行限制和真实 LLM Tool Call 验收。 |
| JSON Runtime Store | `DONE_EXPLICIT` | 可显式为 AgentSession 和 PendingAction 启用本地 JSON 持久化；默认产品入口仍使用内存 Store。 |
| Confirmation Runtime | `DONE_EXPLICIT` | 支持一次性批准、恢复执行和最终收敛；尚未提供 Console/API 命令或正式写操作 Tool。 |
| Session Lease / Fencing | `DONE_EXPLICIT` | RUNNING Session 持有 active run、fence generation、heartbeat 和 lease，旧 owner 失去 fence 后不得继续写入。 |
| Execution Checkpoint / Recovery | `DONE_EXPLICIT` | 记录 drive/model/tool/finalizing checkpoint；仅 `DRIVE_READY` 可自动恢复，in-flight 状态 fail-closed。 |
| Orphan PendingAction Maintenance | `DONE_EXPLICIT` | 提供显式 scan/cleanup，过期未引用 PENDING 可转 EXPIRED，旧终态 orphan 可 CAS 删除。 |
| Persistence / API Server | `TODO` | 不接 FastAPI、数据库、Redis、消息队列或后台 worker。 |
| 完整 Safety / 产品级 Confirmation UX | `TODO` | 必须在后续独立阶段实现。 |
| 历史 HTTP 链路 | `LEGACY_UNAVAILABLE` | 旧跨运行时链路不是当前产品入口。 |

## 配置

产品入口默认读取 `health_agent/.env`。从仓库根目录或 `health_agent/` 目录运行都会解析同一个文件，且 shell 环境变量优先于 `.env`。

推荐本地方式：

```bash
cd health_agent
cp .env.example .env
```

编辑 `health_agent/.env`：

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=60
```

缺少 `LLM_BASE_URL`、`LLM_API_KEY` 或 `LLM_MODEL` 时，Bootstrap 会明确失败。

诊断日志默认不输出完整 prompt、完整健康原文、完整模型响应或 API key。

## 本地 JSON Runtime Store

默认产品入口仍使用 `InMemorySessionStore` 和 `InMemoryPendingActionStore`，因此
`agent.main` 与 `scripts/agent_console.py` 不会自动把会话写入磁盘。Slice 5A
只提供显式注入的本地 JSON Adapter，供后续 CLI/API 在明确配置目录、lease 和
恢复策略后接入。

显式启用方式：

```python
from pathlib import Path

from agent.bootstrap import create_generic_runtime_components_from_env

components = create_generic_runtime_components_from_env(
    storage_mode="json",
    storage_directory=Path("runtime-state"),
)
```

实际目录布局：

```text
runtime-state/
  sessions/
    <sha256(session_id)>.json
    <sha256(session_id)>.lock
  pending-actions/
    <sha256(action_id)>.json
    <sha256(action_id)>.lock
```

Store 使用 SHA-256 文件键防止 path traversal，JSON 内仍保存真实 `session_id` /
`action_id`，读取时会校验文件内容 ID 与请求 ID 一致。`create()` 与 `save()` 在
实体级跨进程 lock 内执行；`save(expected_version=...)` 会重新读取磁盘当前
version 后再做 CAS，不使用进程内缓存覆盖磁盘。

写入顺序为同目录临时文件、UTF-8 写入、flush、fsync、权限设置、`os.replace`
原子替换，以及 POSIX 上 best-effort 目录 fsync。macOS/Linux 使用 `fcntl.flock`，
Windows 使用标准库 `msvcrt.locking` 做 best-effort advisory lock。目录权限默认
尝试设为 `0700`，JSON 与 lock 文件默认尝试设为 `0600`。

注意：JSON 文件是本地明文，可能包含用户消息、assistant 消息、Tool Result 和
PendingAction arguments。本 Slice 不实现静态加密，不声明医疗数据合规能力，只适合
受控本地环境。

## 运行租约、恢复与 orphan 维护

Runtime 在 RUNNING Session 上持久化 `active_run_id`、`run_fence_generation`、
heartbeat、lease 和 execution checkpoint。每次运行必须先 claim ownership，写回前
校验 fence；如果旧 run 的 lease 过期，新 run 可以接管并提升 generation。

恢复策略是保守的：`DRIVE_READY` 表示还没有进入外部模型或工具调用，可自动恢复；
`MODEL_CALL_IN_FLIGHT`、`TOOL_CALL_IN_FLIGHT` 与 `FINALIZING` 都不会自动重放，以避免
重复模型调用、重复工具副作用或覆盖不确定终态。

PendingAction orphan 维护必须显式调用。默认 `dry_run=True` 只返回不含
`arguments` / `result_content` 的摘要；非 dry-run 也只会 CAS 过期未引用的 `PENDING`
和删除超过 retention 的未引用终态 Action。`APPROVED` 与 `EXECUTING` 永不自动重试、
失败或删除。

## 验证

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

真实 LLM 集成测试位于 `tests/integration/test_real_llm_provider.py`。只有显式设置 `RUN_LLM_INTEGRATION=1` 且必要配置存在时才调用真实 LLM；默认 skip。

Phase 2A 真实 Tool Call 集成测试位于 `tests/integration/test_real_tool_call_loop.py`，同样需要显式设置 `RUN_LLM_INTEGRATION=1`。

Phase 2A 验收摘要：

```text
确定性测试：145 个，全部通过，默认跳过 2 个显式真实集成测试
真实模型调用轮数：2
真实工具调用次数：1
真实工具名称：convert_weight_unit
真实转换结果：190 jin → 95 kg
真实入口不经过 INITIAL_PLANNING
```

Phase 2A 边界检查：

```bash
rg "MockProvider|ScriptedModelProvider" agent scripts
rg "eval\\(|exec\\(|subprocess|os\\.system" agent/tools agent/runtime
```

## 当前本地入口

```bash
cd health_agent
python3 -m agent.main
python3 scripts/agent_console.py --user-text "190 斤是多少公斤？请调用可用的重量转换工具，不要自行心算。"
```

当前入口使用通用 GenericAgentLoop，输出安全摘要：

```text
status / modelTurns / toolCalls / answer
```

## 开发阅读顺序

```text
../AGENTS.md
→ AGENTS.md
→ ../docs/architecture.md
→ ../docs/mvp-exec-plan.md
→ ../docs/implementation/phase-2a-read-only-tool-call-loop.md
→ README.md
```

## 边界

- 不做医学诊断，不替代医生意见。
- 不开放 shell tool、任意文件系统 tool 或任意 SQL tool。
- 不把模型输出写成已保存、已确认、已发布或已生效。
- 不记录完整健康原文、认证信息、API key、完整 prompt 或完整 raw response。
- Phase 2A 不实现 FastAPI、数据库、Safety Guard、Confirmation Resume、Memory、Plan 发布、写操作 Tool 或多 Agent。
- Phase 2B Runtime Slice 只提供显式 JSON Store、确认恢复协议、lease/fence、checkpoint、stale recovery 和 orphan 维护；不提供后台 worker、Console/API 确认命令、正式写操作 Tool、Memory 或产品级 Safety。

详细架构见 [`../docs/architecture.md`](../docs/architecture.md)，阶段状态见 [`../docs/mvp-exec-plan.md`](../docs/mvp-exec-plan.md)。
