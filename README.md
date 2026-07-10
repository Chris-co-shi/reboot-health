<div align="center">

# reboot-health

### Python-first health agent runtime

<p>
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Scope" src="https://img.shields.io/badge/Scope-Private%20Single%20User-6C5CE7">
  <img alt="Runtime" src="https://img.shields.io/badge/Runtime-OpenAI--compatible-111827">
</p>

**LLM 负责理解用户任务并决定下一步动作；Agent Runtime 负责模型回合、上下文和运行限制；确定性代码负责工具执行、安全边界、确认、持久化、幂等和审计。**

</div>

本项目不做医学诊断，也不替代医生意见。

## Current Status

当前真实 Python 目录是 [`health_agent/`](health_agent/README.md)。产品运行入口已连接真实 OpenAI-compatible Provider，`INITIAL_PLANNING` 兼容层已完成去污染和真实 LLM 验收。

当前阶段：

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A 通用只读 Tool Call Agent Loop：READY
```

Phase 2A 的已确认实施规范：

[`docs/implementation/phase-2a-read-only-tool-call-loop.md`](docs/implementation/phase-2a-read-only-tool-call-loop.md)

尚未实现：

- 通用 Tool Call Loop。
- 只读健康上下文工具。
- FastAPI 产品 API。
- 数据库、Memory、完整 Safety Guard、Confirmation Pause/Resume。
- Plan 发布与 legacy 业务语义迁移。

仓库中仍保留历史 `backend/`、`clients/flutter/`、`frontend/` 和 `deploy/` 代码；这些目录属于 legacy。Java/Python HTTP 链路和旧 Compose 启动链路当前不可用，不代表当前产品入口。

## Current Runtime Shape

```text
用户输入
→ Runtime 构建必要上下文
→ OpenAI-compatible ModelProvider.complete_turn(...)
→ Assistant content
→ INITIAL_PLANNING 兼容解析
→ AgentRunResult
```

Phase 2A 完成后的目标链路：

```text
用户输入
→ 通用 AgentLoop
→ Assistant content 或原生 Tool Call
→ 只读 ToolExecutor
→ role=tool Result
→ 下一次 Model Turn
→ 最终自然语言回答
```

当前兼容层收到 Tool Call 时仍会明确失败；不要将目标链路描述成已经实现。

## Python Quick Start

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests
```

真实 Provider 配置：

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

也可以使用 shell 环境变量；shell 中的值优先于 `.env`。

本地入口：

```bash
cd health_agent
python3 -m agent.main
python3 scripts/agent_console.py --user-text "想从低强度恢复训练"
```

缺少必要模型配置时，产品入口会直接失败，不会回退到测试替身。

## Documentation

| 文档 | 内容 |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | 当前 Python 模块化单体与 Agent Runtime 架构 |
| [`docs/mvp-exec-plan.md`](docs/mvp-exec-plan.md) | 当前阶段、状态、范围和验收 |
| [`docs/implementation/phase-2a-read-only-tool-call-loop.md`](docs/implementation/phase-2a-read-only-tool-call-loop.md) | Phase 2A 的 IDE/人工开发交接规范 |
| [`docs/decisions/0010-python-modular-monolith-and-agent-loop.md`](docs/decisions/0010-python-modular-monolith-and-agent-loop.md) | 当前长期架构决策 |
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
