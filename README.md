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

当前真实 Python 目录是 [`health_agent/`](health_agent/README.md)。本阶段已经把产品运行入口切到真实 OpenAI-compatible Provider，并保留 `INITIAL_PLANNING` 作为临时兼容业务入口。

尚未完成：

- 完整 Tool Call Loop。
- FastAPI 产品 API。
- 数据库、Memory、完整 Safety Guard、Confirmation Pause/Resume。
- Java/Flutter 到新 Python Runtime 的端到端迁移。

仓库中仍保留历史 `backend/`、`clients/flutter/`、`frontend/` 和 `deploy/` 代码；Java/Python HTTP 链路当前不可用，不属于本阶段修复范围。`deploy/docker-compose.yml` 仍是旧启动链路，不能代表当前 Python 产品入口。

## Runtime Shape

```text
用户输入
→ Runtime 构建必要上下文
→ OpenAI-compatible ModelProvider.complete_turn(...)
→ Assistant content 或 tool_calls
→ 兼容层解析旧 INITIAL_PLANNING JSON
→ 没有 Tool Call 时返回 AgentRunResult
```

当前 `INITIAL_PLANNING` 兼容层不执行 Tool Call；如果模型返回 Tool Call，会明确失败。

## Python Quick Start

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests
```

真实 Provider 需要配置：

```bash
cd health_agent
cp .env.example .env
```

然后编辑 `health_agent/.env`：

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=60
```

也可以使用 shell 环境变量；shell 中的值优先于 `.env`：

```bash
export LLM_BASE_URL="https://api.example.com/v1"
export LLM_API_KEY="replace-with-your-api-key"
export LLM_MODEL="your-model-name"
export LLM_TIMEOUT_SECONDS="60"
```

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
| [`health_agent/README.md`](health_agent/README.md) | 当前 Python Runtime 入口、状态和验证 |
| [`AGENTS.md`](AGENTS.md) | 仓库级协作与边界规则 |
| [`docs/`](docs/README.md) | 历史产品、架构和阶段文档，部分内容待按 Python 模块化单体方向更新 |

## Agent Instructions

| 范围 | 规则 |
|---|---|
| 全仓 | [`AGENTS.md`](AGENTS.md) |
| Python Harness | [`health_agent/AGENTS.md`](health_agent/AGENTS.md) |
| Java legacy | [`backend/AGENTS.md`](backend/AGENTS.md) |
| Flutter legacy | [`clients/flutter/AGENTS.md`](clients/flutter/AGENTS.md) |
| Vue legacy | [`frontend/AGENTS.md`](frontend/AGENTS.md) |
| Deployment legacy | [`deploy/AGENTS.md`](deploy/AGENTS.md) |
