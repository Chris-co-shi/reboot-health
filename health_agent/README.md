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

## 边界

- 不做医学诊断，不替代医生意见。
- 不开放 shell tool、任意文件系统 tool 或任意 SQL tool。
- 不把模型输出写成已保存、已确认、已发布或已生效。
- 不记录完整健康原文、认证信息或无关敏感上下文。

详细规则见 [`AGENTS.md`](AGENTS.md)。
