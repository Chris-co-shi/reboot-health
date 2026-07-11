<div align="center">

# reboot-health

### Python-first health agent runtime

<p>
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Scope" src="https://img.shields.io/badge/Scope-Private%20Single%20User-6C5CE7">
  <img alt="Runtime" src="https://img.shields.io/badge/Runtime-OpenAI--compatible-111827">
</p>

**LLM 负责理解用户任务并决定下一步动作；Agent Runtime 负责模型回合、消息历史、工具调度和运行限制；确定性代码负责工具执行、安全边界、确认、持久化、幂等和审计。**

</div>

本项目不做医学诊断，也不替代医生意见。

## Current Status

当前真实 Python 目录是 [`health_agent/`](health_agent/README.md)。产品运行入口已连接真实 OpenAI-compatible Provider，并默认进入通用 `GenericAgentLoop`；`INITIAL_PLANNING` 只作为显式 legacy compatibility 入口保留。

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A 通用只读 Tool Call Agent Loop：DONE
Phase 2B Runtime 状态、确认、恢复与 JSON 持久化安全基础：DONE_EXPLICIT
Phase 2C Interactive Session & Conversation Context：DONE
Phase 3A 健康领域只读工具：TODO
Phase 3B 产品级 Safety Guard：TODO
```

当前权威计划：

[`docs/mvp-exec-plan.md`](docs/mvp-exec-plan.md)

当前 Phase 2C 实施规范：

[`docs/implementation/phase-2c-interactive-session-cli.md`](docs/implementation/phase-2c-interactive-session-cli.md)

## Current User Experience

当前提供两类本地入口。

`agent.main` 和 `scripts/agent_console.py` 仍是 **one-shot CLI**：

```text
一次用户输入
→ GenericAgentLoop
→ 模型直接回答或调用只读工具
→ 最终答案
→ 进程结束
```

`scripts/agent_chat.py` 是 Phase 2C 新增的 **interactive Session CLI**：

```text
启动交互式 CLI
→ 用户连续输入
→ 同一个 session_id 追加消息
→ 可用显式 JSON Store 跨进程恢复
```

需要明确：

- 单次 Agent Run 内可以发生多次模型回合和 Tool Call。
- one-shot 命令之间默认没有对话连续性。
- interactive CLI 会在同一进程内复用同一组 Runtime Components。
- 默认入口使用内存 Store，退出进程后 Session 消失。
- JSON Store 必须显式指定目录；JSON 文件为本地明文，仅适合受控本地环境。
- Session Message History 只是 Runtime 技术状态，不是长期 Memory 或已确认健康事实。

## Current Runtime Shape

```text
用户输入
→ 产品 Bootstrap
→ GenericAgentLoop
→ OpenAI-compatible ModelProvider.complete_turn(...)
→ Assistant content 或原生 Tool Call
→ 只读 ToolExecutor
→ role=tool Result
→ 下一次 Model Turn
→ AgentRunResult
```

当前正式产品工具只有：

```text
convert_weight_unit：kg / lb / jin 确定性换算
```

显式启用 JSON Store 时，Runtime 可持久化 Session、PendingAction、RUNNING lease 和 execution checkpoint，并提供 stale recovery 与 orphan PendingAction 维护能力。

底层 Confirmation/Recovery 协议不等同于产品 CLI/API 已提供批准、拒绝和恢复入口，也不代表正式写操作 Tool 已上线。

## Python Quick Start

### 1. 环境

```bash
cd health_agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

编辑 `health_agent/.env`：

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=60
```

shell 环境变量优先于 `.env`。缺少必要模型配置时，产品入口会明确失败，不会回退测试替身。

### 2. 当前直接使用

```bash
cd health_agent
python3 -m agent.main --user-text "190 斤是多少公斤？请调用工具计算。"
python3 scripts/agent_console.py --user-text "用简单的话解释渐进超负荷。"
```

每个命令都是一次独立用户请求。

交互式连续对话：

```bash
cd health_agent
python3 scripts/agent_chat.py
```

显式 JSON Session 恢复：

```bash
python3 scripts/agent_chat.py \
  --storage json \
  --storage-directory runtime-state \
  --session-id chris-main
```

支持命令：`/help`、`/new`、`/status`、`/resume <session-id>`、`/exit`。
`/resume` 只切换已存在 Session；Session 不存在时不会调用模型。

### 3. 验证

```bash
cd health_agent
python3 -m compileall agent tests scripts
python3 -m unittest discover -s tests -v
```

## Session、Context 与 Memory

项目明确区分：

```text
Session Message History ≠ 长期 Memory
Conversation Summary ≠ 已确认健康事实
UserProfile / HealthConstraint / Plan ≠ 模型记忆
Memory Candidate ≠ 自动生效的领域事实
```

详细决策：

[`docs/decisions/0011-session-context-memory-boundaries.md`](docs/decisions/0011-session-context-memory-boundaries.md)

## 尚未实现

- 默认 one-shot 入口隐式持久化与恢复。
- 真实用户档案、健康约束、计划和训练记录读取。
- Console/API 的确认、拒绝和恢复入口。
- 正式写操作 Tool 与计划发布。
- FastAPI 产品 API。
- 数据库、完整 Safety Guard 和正式 Memory Candidate 闭环。
- Flutter/Web 正式客户端链路。

仓库中保留的 `backend/`、`clients/flutter/`、`frontend/` 和 `deploy/` 属于 legacy。旧 Java/Python HTTP 链路和 Compose 启动链路当前不可用，不代表当前产品入口。

## Documentation

| 文档 | 内容 |
|---|---|
| [`docs/product-scope.md`](docs/product-scope.md) | 产品定位、体验、范围与非目标 |
| [`docs/architecture.md`](docs/architecture.md) | 当前 Python 模块化单体与 Agent Runtime 架构 |
| [`docs/mvp-exec-plan.md`](docs/mvp-exec-plan.md) | 当前阶段、状态、范围和验收 |
| [`docs/implementation/phase-2c-interactive-session-cli.md`](docs/implementation/phase-2c-interactive-session-cli.md) | 当前 Phase 2C 工程交接规范 |
| [`docs/decisions/0010-python-modular-monolith-and-agent-loop.md`](docs/decisions/0010-python-modular-monolith-and-agent-loop.md) | Python-first 与通用 Agent Loop 决策 |
| [`docs/decisions/0011-session-context-memory-boundaries.md`](docs/decisions/0011-session-context-memory-boundaries.md) | Session、Context、Memory 与领域事实边界 |
| [`health_agent/README.md`](health_agent/README.md) | Python Runtime 入口和验证 |
| [`AGENTS.md`](AGENTS.md) | 仓库级协作与边界规则 |
| [`docs/`](docs/README.md) | 文档索引与阅读路径 |

## Agent Instructions

| 范围 | 规则 |
|---|---|
| 全仓 | [`AGENTS.md`](AGENTS.md) |
| Python Runtime | [`health_agent/AGENTS.md`](health_agent/AGENTS.md) |
| 文档 | [`docs/AGENTS.md`](docs/AGENTS.md) |
| Java legacy | [`backend/AGENTS.md`](backend/AGENTS.md) |
| Flutter legacy | [`clients/flutter/AGENTS.md`](clients/flutter/AGENTS.md) |
| Vue legacy | [`frontend/AGENTS.md`](frontend/AGENTS.md) |
| Deployment legacy | [`deploy/AGENTS.md`](deploy/AGENTS.md) |
