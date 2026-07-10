# 仓库级 Agent 规则

## 语言要求

- 所有说明、计划、总结、自查结果必须使用中文。
- 代码中的变量名、类名、方法名遵循项目既有语言和命名习惯，不强制中文。
- 注释优先使用中文，除非项目已有英文注释约定。

## 当前架构方向

`reboot-health` 正在从历史 Java/Python/Flutter 多运行时方案迁移为 Python 模块化单体。

新的核心原则：

```text
LLM 负责理解用户任务并决定下一步动作；
Agent Runtime 负责模型循环、上下文、工具调度、暂停恢复和运行限制；
确定性代码负责工具执行、数据校验、安全阻断、确认、持久化、幂等和审计。
```

当前真实 Python 主目录是 `health_agent/`，规则见 `health_agent/AGENTS.md`。

当前长期决策见：

```text
docs/decisions/0010-python-modular-monolith-and-agent-loop.md
```

## 当前阶段约束

- Phase 1、1.1、1.2、1.3 已完成真实 LLM Provider、配置收口、真实连接验收和兼容层去污染。
- Phase 2A 状态为 `READY`，尚未实现。
- Phase 2A 的唯一实施交接规范是 `docs/implementation/phase-2a-read-only-tool-call-loop.md`。
- 产品运行 Provider 为 OpenAI-compatible `ModelProvider.complete_turn(...)`。
- 产品 LLM 配置使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`；Bootstrap 从 `health_agent/.env` 加载，shell 环境变量优先。
- `INITIAL_PLANNING` 仍是临时兼容业务入口，不代表最终 Agent 架构。
- 通用 Tool Call Loop、FastAPI、数据库、Memory、完整 Safety、Confirmation Resume、Plan 发布和 DailyRecord 尚未实现。
- 历史 `backend/`、`clients/flutter/`、`frontend/`、`deploy/` 默认视为 legacy；未经用户明确要求不得扩展其业务能力。
- Java/Python HTTP 链路当前不可用，不得在未获授权时顺手修复。
- 不得把未运行、未构建、未真实验收的能力写成 `DONE`。

## 开发前阅读顺序

实施 Phase 2A 前必须按顺序读取：

```text
AGENTS.md
→ health_agent/AGENTS.md
→ docs/architecture.md
→ docs/mvp-exec-plan.md
→ docs/implementation/phase-2a-read-only-tool-call-loop.md
→ health_agent/README.md
```

如上述文档与代码冲突，先报告冲突，不得自行扩大范围或降低验收标准。

## 任务契约

开始修改前，必须明确：

```text
Primary Module:
Allowed Paths:
Forbidden Paths:
Required Verification:
Out of Scope:
```

规则：

- 每个任务只能有一个主模块。
- 默认优先在 `health_agent/` 内实施。
- 跨 legacy 运行时任务必须先定义接口、Schema 或 Tool Contract，再分别实施。
- 不允许在没有说明理由的情况下扩大任务范围。
- 不允许为了让测试通过而降低业务规则、删除测试、放宽断言或绕过校验。
- 不允许主动新增生产依赖；确需新增时，必须先说明原因、替代方案和影响范围。
- 不允许大规模重构，除非实施规范明确要求且代码现状确实无法小步迁移。
- 不允许把临时实现伪装成最终实现。

## Python Runtime 边界

Agent Runtime 只负责：

- Session。
- Model Turn。
- Tool Call Loop。
- 最大轮次。
- 超时。
- 错误收敛。
- 后续 Confirmation Pause 状态协议。
- Event/Trace。

Provider 只负责：

- 调用模型。
- 转换 system/user/assistant/tool 消息。
- 转换 Tool Schema。
- 解析 Assistant Response。
- 解析 Tool Calls。
- 归一化错误。
- 返回 Usage 和 Provider Metadata。

Provider 不得知道 Program、Phase、WeeklyPlan、TodayAction、PlanVersion 或 HealthConstraint。

Tool Runtime 负责：

- ToolRegistry 白名单。
- ToolDefinition 模型可见合同。
- 参数、权限和副作用校验。
- ToolExecutor 确定性执行。
- 结构化 Tool Result 和错误。

Phase 2A 只允许只读或纯计算 Tool，不允许写操作、数据库访问、发布或确认。

测试替身只能放在 `health_agent/tests/`，不得被产品 Bootstrap 引用。

## 修改原则

- 优先最小修改。
- 优先遵循现有结构，先搜索再决定是否新增文件。
- 优先补齐缺失点，不建立第二套重复 Contract。
- 遇到不确定信息时，先在仓库中搜索，不允许凭经验猜测。
- 如果发现规则冲突，必须暂停并说明冲突点。
- 修改前检查工作区；不覆盖、不删除、不 stash 用户未提交修改。
- 不在仓库中写入真实健康资料、密钥、数据库密码、本机绝对路径或完整认证凭据。
- Trace 和日志不得记录完整健康原文、完整 prompt、raw model response、API key 或认证信息。

## 禁止能力

未经独立阶段批准，不得新增：

- Shell Tool、任意文件系统 Tool、任意 SQL Tool。
- 写操作 Tool。
- Safety Guard 半成品。
- Confirmation 状态机半成品。
- FastAPI、数据库、Redis、消息队列。
- 多 Agent、Subagent、DAG 或工作流引擎。
- 普通文本伪 Tool Call 解析。
- Mock/Fake/Smoke 产品路径。

## 文档唯一事实来源

- 项目入口和当前摘要：`README.md`
- 当前架构：`docs/architecture.md`
- 当前阶段与验收状态：`docs/mvp-exec-plan.md`
- 已确认阶段的实施交接：`docs/implementation/`
- Python Runtime 入口和验证：`health_agent/README.md`
- 长期决策：`docs/decisions/`

历史文档与 legacy 代码不得被描述成当前可运行能力。

## 验证命令

仅执行与本次任务相关的命令，并如实报告未验证项。

```bash
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests -v

cd ..
git diff --check
```

Phase 2A 还必须执行实施规范要求的产品测试替身搜索、任意代码执行能力搜索和真实 LLM Tool Call 验收。

## 完成定义

完成报告必须包含：

- 修改、新增和删除文件；
- 实际执行的验证命令与结果；
- 真实 LLM 是否发生 Tool Call；
- 实际模型回合数和工具调用次数；
- 是否经过 `INITIAL_PLANNING`；
- 当前环境无法验证的内容；
- 未完成事项和风险；
- 是否越过原任务边界。
