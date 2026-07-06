# Python Health Agent Backend 规则

## 定位

`health_agent/` 是 reboot-health 的 Python-first Health Agent Backend，负责产品智能、任务编排、Skill 调用、候选生成和运行轨迹。它不是通用开发 Agent，也不是简单模型代理。

Java Health Domain Kernel 仍是已确认事实、安全规则、权限、确认、审计、幂等和领域状态权威。

## Intent Layer

- Core 是 narrow waist：只做请求归一化、Skill 分发、错误收敛和运行边界。
- Capability lives at the edges：能力应放在 Skills、Tools、Memory、Models、Domain、Persistence、Storage 或 Plugins。
- 新增健康能力优先新增或扩展 Skill，不要膨胀 `agent/runtime/core.py`。
- 新增 Tool 必须通过 ToolRegistry 注册，声明权限、影响等级、输入输出 Schema、确认策略、幂等策略、超时和审计策略。
- Agent 不得直接访问 DB、Redis、文件系统或 shell。
- Agent Loop、LLM、Prompt 不得直接访问 PostgreSQL、Redis、文件系统或任意外部资源。
- Tool 内部可以调用 Domain Service；Domain Service 可以调用 Repository；Repository 才负责数据库访问。
- MemoryCandidate 不等于 confirmed memory。
- 健康安全规则优先于模型输出。
- 重要健康事实、健康约束、目标、计划发布和训练负荷增加必须等待用户确认。
- `.env` 只放 secrets；非 secret 配置后续放 `agent/settings.py` 或独立 config。

## 当前阶段

- `INITIAL_PLANNING` single-shot skill 已完成。
- 当前默认 Provider 是 `MockProvider`。
- PostgreSQL、Redis、FastAPI、真实模型、多 Agent、消息队列和向量数据库暂未接入。
- Agent Loop、Tool 执行、Memory 持久化、插件加载仍是后续纵向切片，不得宣称已经完成。

## 目录规则

- `agent/runtime/`：Core、Loop、Session、Context、Trace、State。
- `agent/models/`：模型 Provider 抽象和实现。
- `agent/tools/`：Tool Contract、Registry、Executor 和内置 Tool 预留。
- `agent/skills/`：Python Skill 实现、Skill 协议和 Skill Registry。
- `agent/memory/`：MemoryCandidate、Manager、Summary 和 Provider 预留。
- `agent/domain/`：健康领域服务预留边界。
- `agent/persistence/`：DB/Repository 预留边界。
- `agent/api/`：API 层预留边界，当前不接 Web 框架。
- `agent/storage/`：受控文件存储边界。
- `agent/schemas/`：跨层传输 Schema。
- `skills/`：外置 Skill 资产，如 Prompt、示例和评测。
- `prompts/`：公共系统边界、安全规则和输出合同。
- `plugins/`：后续插件机制预留。

## 禁止

- 不开放 shell tool、任意文件系统 tool 或任意 SQL tool。
- 不连接 PostgreSQL 或 Redis，除非任务明确进入对应纵向切片。
- 不接真实模型，除非任务明确要求并完成配置与安全评估。
- 不直接发布 PlanVersion 或修改已确认事实。
- 不把 AI 输出写成已保存、已确认、已发布或已生效。
- 不为了测试通过而删除测试、放宽断言、绕过校验或降低业务规则。
- 不记录完整健康原文、密钥、令牌或认证信息。

## 验证命令

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests
```
