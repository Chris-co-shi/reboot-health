# Python Health Agent Backend 规则

## 定位

`health_agent/` 是 reboot-health 当前真实 Python Health Agent Runtime，负责模型回合、运行边界、Skill 兼容层、Tool 合同骨架和运行轨迹。它不是通用开发 Agent，也不是简单模型代理。

仓库中仍保留历史 Java/Flutter/部署代码，但当前重构方向是 Python 模块化单体；未经用户明确要求，不在本目录任务中修复旧 Java/Python HTTP 链路。

## Intent Layer

- Core 是 narrow waist：只做请求归一化、Skill 分发、错误收敛和运行边界。
- Capability lives at the edges：能力应放在 Skills、Tools、Memory、Models、Domain、Persistence、Storage 或 Plugins。
- 新增健康能力优先新增或扩展 Skill，不要膨胀 `agent/runtime/core.py`。
- 产品 Provider 必须通过 `agent/bootstrap.py` 注入，不得在 Core、Loop 或 Skill 内自行创建。
- 新增 Tool 必须通过 ToolRegistry 注册，声明权限、影响等级、输入输出 Schema、确认策略、幂等策略、超时和审计策略。
- 当前 ToolExecutor 仍只是 skeleton，不得宣称已经具备真实业务工具调用能力。
- Agent 不得直接访问 DB、Redis、文件系统或 shell。
- Agent Loop、LLM、Prompt 不得直接访问 PostgreSQL、Redis、文件系统或任意外部资源。
- Tool 内部可以调用 Domain Service；Domain Service 可以调用 Repository；Repository 才负责数据库访问。
- MemoryCandidate 不等于 confirmed memory，不得宣称已经沉淀为长期记忆、已确认事实或用户档案。
- 健康安全规则优先于模型输出。
- 重要健康事实、健康约束、目标、计划发布和训练负荷增加必须等待用户确认。
- 产品 LLM 配置使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`。
- `.env` 的规范路径是 `health_agent/.env`，只允许 Bootstrap 或 Bootstrap 直接调用的配置加载函数读取；shell 环境变量优先于 `.env`。
- 普通 unittest 不允许调用真实模型、网络、数据库或外部服务；测试替身只能放在 `tests/`。

## Harness 长期规则

- 运行结果必须能被结构化审计：`AgentRunResult` 是外部合同，`RunTrace` 是运行摘要。
- QualityGate 发现项必须保留结构化形式；`warnings` 只作为兼容摘要。
- Trace 和日志不得记录完整健康原文、完整 prompt、raw model response、API key 或认证信息。
- 当前不是 ReAct，不是 Autonomous Agent；未实现 structured multi-step loop 前不得使用相关完成口径。
- 候选、草案、解释都不是业务事实；确认、发布、保存和审计仍属于后续权威边界。

## 当前阶段

- `INITIAL_PLANNING` 仍是临时兼容业务入口。
- 产品运行 Provider 是 OpenAI-compatible `ModelProvider.complete_turn(...)`。
- AgentLoop、AgentRunResult、RunTrace、PlanningQualityGate 已接入兼容路径。
- 真实 LLM 集成测试必须显式配置环境变量；缺少配置时 skip。
- ToolExecutor 仍是 skeleton；没有 shell/file/sql tool。
- Memory 当前只有 MemoryCandidate，不持久化、不自动确认。
- PostgreSQL、Redis、FastAPI、Java Runtime API、正式 Persistence、多 Agent、MCP、消息队列和向量数据库暂未接入。

## 目录规则

- `agent/runtime/`：Core、Loop、Session、Context、Trace、State。
- `agent/models/`：通用 ModelProvider 合同和 OpenAI-compatible Provider。
- `agent/tools/`：Tool Contract、Registry、Executor 和内置 Tool 预留。
- `agent/skills/`：Python Skill 实现、Skill 协议和 Skill Registry；当前 `INITIAL_PLANNING` 是兼容层。
- `agent/memory/`：MemoryCandidate、Manager、Summary 和 Provider 预留。
- `agent/domain/`：健康领域服务预留边界。
- `agent/persistence/`：DB/Repository 预留边界。
- `agent/api/`：API 层预留边界，当前不接 Web 框架。
- `agent/storage/`：受控文件存储边界。
- `agent/schemas/`：跨层传输 Schema。
- `skills/`：外置 Skill 资产，如 Prompt、示例和评测。
- `prompts/`：公共系统边界、安全规则和输出合同。
- `plugins/`：后续插件机制预留。
- `tests/support/`：测试专用 Provider 和测试辅助实现，产品代码不得引用。

## 禁止

- 不开放 shell tool、任意文件系统 tool 或任意 SQL tool。
- 不连接 PostgreSQL 或 Redis，除非任务明确进入对应纵向切片。
- 不新增其他模型供应商框架；当前只支持 OpenAI-compatible Chat Completions。
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
