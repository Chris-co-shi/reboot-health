# Python-first Health Agent Backend

`health_agent` 是 reboot-health 的 Python-first Health Agent Backend。它不是普通健康 CRUD，也不是单纯聊天框；它负责把用户自然语言转成可审计的候选理解、计划草案、今日行动和后续确认请求。

当前核心闭环：

```text
natural language -> understanding candidate -> confirmation -> plan draft -> today action -> feedback -> memory candidate
```

Java Health Domain Kernel 仍是已确认事实、安全规则、权限、确认、审计、幂等和领域状态权威。Python 输出只能是候选、草案或解释。

## 架构原则

- `agent/runtime` 是 narrow waist，只做触发归一化、Skill 分发和运行边界收敛。
- 能力放在边缘：`skills`、`tools`、`memory`、`models`、`domain`、`persistence` 后续按纵向切片扩展。
- 健康能力优先通过 Skill 增加，不膨胀 Core。
- Agent 只能调用 ToolRegistry 中注册的白名单 Tool。
- Agent Loop、LLM、Prompt 不直接访问 PostgreSQL、Redis、文件系统或任意外部资源。
- AI 输出不是确认事实；重要健康事实、健康约束、目标和计划发布必须等待用户确认。

## 目录结构

```text
health_agent/
  agent/
    runtime/        # Core、Loop、Session、Context、Trace、State
    models/         # Mock 与 OpenAI-compatible Provider 接口实现
    tools/          # Tool contract、registry、executor
    skills/         # Python Skill 实现与 Registry
    memory/         # MemoryCandidate 与管理骨架
    domain/         # 健康领域服务预留边界
    persistence/    # Repository/DB 预留边界
    api/            # API 层预留边界，当前不接 Web 框架
    storage/        # 受控文件存储边界
    schemas/        # Agent、Planning、Tool、Memory、Health Schema
  skills/           # 外置 Skill 资产
  prompts/          # 公共 Prompt 边界与输出合同
  plugins/          # 后续插件扩展预留
  scripts/          # 本地验证脚本
  tests/            # unittest 测试
```

## 当前状态

- `INITIAL_PLANNING` single-shot skill 已完成。
- `MockProvider` 保持本地测试稳定。
- Harness Core Skeleton 已按 Python-first 结构落位。
- PostgreSQL、Redis、FastAPI、真实模型暂未接入。
- Agent Loop、Tool 执行、Memory 持久化、插件加载仍是后续纵向切片。

## Harness 阶段命名

当前项目主线仍是 Python Agent Harness，不是 ReAct，也不是完整 Autonomous Agent。

- L0 Provider Harness：基本完成，OpenAI-compatible Provider 与 MockProvider 可用。
- L1 Single-shot Skill Harness：技术链路完成，`INITIAL_PLANNING` 可运行到 `waiting_confirmation`。
- L2 Trace + Eval Harness：当前阶段，目标是稳定 trace summary 与 eval cases。
- L3 ReAct Loop Harness：未开始。
- L4 Tool Harness：未开始。
- L5 Memory Harness：未完成，当前只有 MemoryCandidate。
- L6 Autonomy Policy：未开始。

## Quick Start

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests
```

Smoke run：

```bash
cd health_agent
python3 scripts/smoke_initial_planning.py
```

或：

```bash
cd health_agent
python3 -m agent.main
```

## 诊断运行模式

诊断配置从 `.env` 或 shell 环境读取；CLI 参数只作为本次 smoke 的显式覆盖。
优先级为：

```text
CLI 参数 > 环境变量 > 安全默认值
```

安全默认值：

```bash
REBOOT_HEALTH_MODEL_DEBUG_LOG=false
REBOOT_HEALTH_MODEL_LOG_REQUEST=none
REBOOT_HEALTH_MODEL_LOG_RESPONSE=none
REBOOT_HEALTH_AGENT_DEBUG_TRACE=false
```

### normal

默认模式只输出脱敏摘要，不打印 trace、prompt、用户原文或模型返回正文。

```bash
cd health_agent
python3 scripts/smoke_initial_planning.py
```

### trace

用于查看本次 AgentRun 的脱敏 trace。`--print-trace` 只控制 stdout 是否包含
trace；`REBOOT_HEALTH_AGENT_DEBUG_TRACE=true` 控制 Skill 阶段诊断日志。

```bash
cd health_agent
REBOOT_HEALTH_AGENT_DEBUG_TRACE=true \
python3 scripts/smoke_initial_planning.py --print-trace
```

### deep-debug

用于真实 OpenAI-compatible Provider 排查。`--model-debug-log` 只打开 provider
shape 级别日志，不会自动打印 request/response 正文。模型请求和返回正文只能通过
环境变量显式打开：

```bash
cd health_agent
REBOOT_HEALTH_AGENT_PROVIDER=openai-compatible \
REBOOT_HEALTH_MODEL_DEBUG_LOG=true \
REBOOT_HEALTH_MODEL_LOG_REQUEST=preview \
REBOOT_HEALTH_MODEL_LOG_RESPONSE=preview \
REBOOT_HEALTH_AGENT_DEBUG_TRACE=true \
python3 scripts/smoke_initial_planning.py --print-draft-summary --print-trace --model-debug-log
```

`REBOOT_HEALTH_MODEL_LOG_REQUEST` 和 `REBOOT_HEALTH_MODEL_LOG_RESPONSE` 支持
`none|preview|raw`。`raw` 只用于本地临时诊断，可能打印完整 prompt 或模型返回正文。

## 边界

- 不做医学诊断，不替代医生意见。
- 不开放 shell tool、任意文件系统 tool 或任意 SQL tool。
- 不把模型输出写成已保存、已确认、已发布或已生效。
- 不记录完整健康原文、认证信息或无关敏感上下文。

详细规则见 [`AGENTS.md`](AGENTS.md)。
