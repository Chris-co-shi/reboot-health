# Python health-agent Runtime

`health_agent/` 是 reboot-health 当前已验证的 Python Agent Runtime，也是未来独立 `health-agent` 服务的迁移基础。

它当前提供本地 CLI、内存/JSON Store 和 Phase 1–2C Runtime 能力；它**不是** Health Platform、生产 API/Worker、PostgreSQL/Redis 部署或完整健康产品。

## 当前状态

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A Tool Call Agent Loop：DONE
Phase 2B Runtime safety foundation：DONE_EXPLICIT
Phase 2C Interactive Session：DONE
Architecture Freeze：FROZEN
```

后续路线以 [`../docs/PHASE_STATUS.md`](../docs/PHASE_STATUS.md) 为准。Phase 3B Slice 1 仅完成仓库重组和服务定位，不改变 Runtime 行为。

## 已实现能力

| 能力 | 状态 |
|---|---|
| OpenAI-compatible Provider | `DONE` |
| GenericAgentLoop | `DONE` |
| system/user/assistant/tool 消息 | `DONE` |
| ToolRegistry / ToolExecutor | `DONE` |
| `convert_weight_unit` | `DONE` |
| JSON Session/PendingAction Store | `DONE_EXPLICIT` |
| lease / heartbeat / fencing | `DONE_EXPLICIT` |
| checkpoint / stale recovery | `DONE_EXPLICIT` |
| orphan PendingAction maintenance | `DONE_EXPLICIT` |
| interactive Session CLI | `DONE` |
| PostgreSQL Task/Run、API/Worker、Redis Streams | `TODO` |
| Platform Tool API、RAG、Sub-Agent、Sandbox | `TODO` |

## 目标边界

未来 health-agent 只负责通用执行：

- Task、Run、Step、Checkpoint。
- Model、Tool、预算和 Provider fallback。
- Context、Summary、RAG 和 Sub-Agent。
- Sandbox、Trace、Outbox 和恢复。

Health Platform 负责用户、Conversation、Fact、Plan、Risk、File、Secret、确认和业务审计。health-agent 不直接连接 Platform 数据库，不发布正式 Plan，也不把模型结果写成业务事实。

完整架构见：

- [`../docs/SYSTEM_ARCHITECTURE.md`](../docs/SYSTEM_ARCHITECTURE.md)
- [`../docs/STATE_MACHINES.md`](../docs/STATE_MACHINES.md)
- [`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md)
- [`../docs/SECURITY_AND_PRIVACY.md`](../docs/SECURITY_AND_PRIVACY.md)

## 配置

```bash
cd health_agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=60
```

shell 环境变量优先于 `health_agent/.env`。缺少必要配置时明确失败，不回退测试替身。

## One-shot CLI

```bash
python3 -m agent.main --user-text "190 斤是多少公斤？请调用工具计算。"
python3 scripts/agent_console.py --user-text "解释渐进超负荷。"
```

每个命令是独立进程和新的默认内存 Store。

## Interactive Session CLI

```bash
python3 scripts/agent_chat.py
```

显式 JSON 恢复：

```bash
python3 scripts/agent_chat.py \
  --storage json \
  --storage-directory runtime-state \
  --session-id chris-main
```

命令：`/help`、`/new`、`/status`、`/resume <session-id>`、`/exit`。

JSON Store 使用本地明文，可能包含用户和模型消息，仅适合受控开发环境。

## Runtime 恢复语义

- `DRIVE_READY`：可自动恢复。
- `MODEL_CALL_IN_FLIGHT`：默认不重放。
- `TOOL_CALL_IN_FLIGHT`：默认不重放。
- `FINALIZING`：先对账终态，不自动覆盖。

新 owner 必须获得更高 fence generation；旧 owner 失去写权限。

## 验证

```bash
python3 -m compileall agent tests scripts
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_json_store_multiprocess -v
python3 -m unittest tests.test_run_lease_multiprocess -v
python3 -m unittest tests.test_stale_recovery -v
python3 -m unittest tests.test_orphan_pending_actions -v
```

真实 LLM 集成测试必须显式设置 `RUN_LLM_INTEGRATION=1`，并且不得提交 API Key、完整 Prompt、完整响应或真实健康数据。

## 开发规则

读取 [`AGENTS.md`](AGENTS.md)。没有对应 `READY`/`IN_PROGRESS` implementation 规范时禁止实现后续能力。
