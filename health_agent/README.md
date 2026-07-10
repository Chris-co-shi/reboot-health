# Python Health Agent Runtime

`health_agent/` 是 reboot-health 当前与目标 Python Runtime。产品运行入口直接使用 OpenAI-compatible Chat Completions Provider，不会在配置缺失时回退到测试替身。

当前状态：

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A 通用只读 Tool Call Agent Loop：READY，尚未实现
```

Phase 2A 开发前必须读取：

[`../docs/implementation/phase-2a-read-only-tool-call-loop.md`](../docs/implementation/phase-2a-read-only-tool-call-loop.md)

## 当前运行模型

```text
用户输入
→ AgentCore / AgentLoop
→ InitialPlanningSkill 兼容层
→ ModelProvider.complete_turn(messages, tools, options)
→ OpenAI-compatible Chat Completions
→ ModelResponse.content
→ PlanningOutput 兼容解析与校验
```

`INITIAL_PLANNING` 已完成真实 LLM 验收和去污染，但仍是临时兼容入口，不代表最终 Agent 架构。

当前尚未实现完整 Tool Call Loop。兼容层收到模型 Tool Call 时会明确失败。

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
| 产品 Bootstrap | `DONE` | 加载 `health_agent/.env` 并创建真实 Provider。 |
| INITIAL_PLANNING | `LEGACY_COMPAT` | 真实 LLM 可运行；不再注入固定健康事实；后续显式隔离。 |
| 通用 ModelMessage Tool 消息 | `PARTIAL` | 已有 Tool Call 数据结构，尚未完成 assistant/tool 往返消息。 |
| ToolRegistry / ToolExecutor | `SKELETON` | 尚无真实产品 Tool 执行链路。 |
| Tool Call Agent Loop | `READY` | 设计与验收已确认，尚未实现。 |
| Persistence / API Server | `TODO` | 不接 FastAPI、数据库、Redis 或消息队列。 |
| Safety / Confirmation | `TODO` | 必须在后续独立阶段实现。 |
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

## 验证

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests -v
```

真实 LLM 集成测试位于 `tests/integration/test_real_llm_provider.py`。只有显式设置 `RUN_LLM_INTEGRATION=1` 且必要配置存在时才调用真实 LLM；默认 skip。

Phase 2A 完成前还必须执行：

```bash
rg "MockProvider|ScriptedModelProvider" agent scripts
rg "eval\\(|exec\\(|subprocess|os\\.system" agent/tools agent/runtime
```

并完成真实 Tool Call 验收，详见实施规范。

## 当前本地入口

```bash
cd health_agent
python3 -m agent.main
python3 scripts/agent_console.py --user-text "想从低强度恢复训练"
```

当前入口仍进入 `INITIAL_PLANNING` 兼容路径。Phase 2A 实施后，main 和 console 才切换为通用 AgentLoop。

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

详细架构见 [`../docs/architecture.md`](../docs/architecture.md)，阶段状态见 [`../docs/mvp-exec-plan.md`](../docs/mvp-exec-plan.md)。
