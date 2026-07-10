# Python Health Agent Harness

`health_agent/` 是 reboot-health 当前真实 Python Runtime 目录。产品运行入口直接使用 OpenAI-compatible Chat Completions Provider，不会在配置缺失时回退到测试替身。

当前仍处于 `INITIAL_PLANNING` 兼容阶段：旧 Planning Prompt、PlanningInput、PlanningOutput 和 Schema 暂时保留；Provider 已迁移到通用 Model Turn Contract。

## 运行模型

```text
用户输入
→ AgentCore / AgentLoop
→ InitialPlanningSkill 兼容层
→ ModelProvider.complete_turn(messages, tools, options)
→ OpenAI-compatible Chat Completions
→ ModelResponse.content
→ PlanningOutput 兼容解析与校验
```

本阶段尚未实现完整 Tool Call Loop。`INITIAL_PLANNING` 兼容层收到模型 Tool Call 时会明确失败。

## 目录结构

```text
health_agent/
  agent/
    bootstrap.py     # 产品 Composition Root
    runtime/         # Core、Loop、Session、Trace、State
    models/          # 通用 ModelProvider 合同与 OpenAI-compatible Provider
    tools/           # Tool contract、registry、executor 骨架
    skills/          # 临时 INITIAL_PLANNING 兼容 Skill
    schemas/         # Agent、Planning、Tool、Memory、Health Schema
    memory/          # MemoryCandidate 骨架，不持久化
    api/             # API 层预留，当前不接 Web 框架
  skills/            # 外置 Prompt 与 Skill metadata
  prompts/           # 公共 Prompt 边界
  scripts/           # 本地 console
  tests/             # unittest 和测试专用 scripted provider
```

测试替身只允许存在于 `tests/`，产品 Bootstrap 不引用测试目录。

## 当前状态

| 能力 | 状态 | 说明 |
|---|---|---|
| OpenAI-compatible Provider | 已接入 | 实现 `complete_turn()`，支持普通文本、Tool Call、usage 和 metadata。 |
| 产品 Bootstrap | 已接入 | `agent.bootstrap.create_agent_core_from_env()` 加载 `health_agent/.env` 后创建真实 Provider。 |
| INITIAL_PLANNING | 兼容中 | 旧业务入口保留，Provider 不再解析 PlanningOutput。 |
| Tool Call Loop | 未实现 | 当前只完成模型 Tool Call 数据结构和 Provider 转换。 |
| Persistence / API Server | 未实现 | 不接 FastAPI、数据库、Redis 或消息队列。 |
| Java/Python HTTP 链路 | 不可用 | 历史链路仍在仓库中，本阶段不修复。 |

## 配置

产品入口默认读取 `health_agent/.env`。从仓库根目录或 `health_agent/` 目录运行都会解析同一个文件，且 shell 环境变量优先于 `.env`。

推荐本地方式：

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

也可以使用 shell 环境变量：

```bash
export LLM_BASE_URL="https://api.example.com/v1"
export LLM_API_KEY="replace-with-your-api-key"
export LLM_MODEL="your-model-name"
export LLM_TIMEOUT_SECONDS="60"
```

缺少 `LLM_BASE_URL`、`LLM_API_KEY` 或 `LLM_MODEL` 时，Bootstrap 会明确失败。

```bash
REBOOT_HEALTH_AGENT_DEBUG_TRACE=false
```

诊断日志默认不输出完整 prompt、完整健康原文、完整模型响应或 API key。

## 验证

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests
```

真实 LLM 集成测试位于 `tests/integration/test_real_llm_provider.py`。只有显式设置 `RUN_LLM_INTEGRATION=1`、`LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL` 时才会调用真实 LLM；默认会 skip。

## 本地入口

```bash
cd health_agent
python3 -m agent.main
python3 scripts/agent_console.py --user-text "想从低强度恢复训练"
```

这些入口都会使用产品 Bootstrap。没有模型环境变量时会失败，不会使用测试替身。

## 边界

- 不做医学诊断，不替代医生意见。
- 不开放 shell tool、任意文件系统 tool 或任意 SQL tool。
- 不把模型输出写成已保存、已确认、已发布或已生效。
- 不记录完整健康原文、认证信息、API key、完整 prompt 或完整 raw response。
- 当前不实现 FastAPI、数据库、完整 Safety、Confirmation Resume、Memory 或 Plan 发布。

详细规则见 [`AGENTS.md`](AGENTS.md)。
