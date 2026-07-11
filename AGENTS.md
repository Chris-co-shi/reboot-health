# 仓库级 Agent 规则

## 语言要求

- 所有说明、计划、总结和自查结果必须使用中文。
- 代码变量名、类名和方法名遵循项目既有命名习惯。
- 注释优先使用中文，除非所在文件已有英文约定。

## 当前架构方向

`reboot-health` 正在从历史 Java/Python/Flutter 多运行时方案迁移为 Python-first 模块化单体。

```text
LLM 负责理解用户任务并决定下一步动作；
Agent Runtime 负责模型循环、消息历史、工具调度、暂停恢复和运行限制；
确定性代码负责工具执行、数据校验、安全阻断、确认、持久化、幂等和审计。
```

当前真实 Python 主目录是 `health_agent/`。

长期决策：

```text
docs/decisions/0010-python-modular-monolith-and-agent-loop.md
docs/decisions/0011-session-context-memory-boundaries.md
```

## 当前阶段约束

- Phase 1、1.1、1.2、1.3 已完成。
- Phase 2A 通用只读 Tool Call Agent Loop 已完成并经过真实 LLM Tool Call 验收。
- Phase 2B Runtime 状态、确认、恢复与 JSON 持久化安全基础已完成显式能力。
- 默认 `agent.main` 和 `scripts/agent_console.py` 仍是 one-shot、内存 Store 入口。
- 当前下一阶段是 Phase 2C Interactive Session & Conversation Context。
- Phase 2C 只建设连续对话 CLI、显式 JSON Session 恢复和必要的产品入口组装。
- 健康领域 Repository、健康只读工具、数据库、长期 Memory、完整 Safety、正式写操作和 FastAPI 尚未实现。
- `INITIAL_PLANNING` 是显式 legacy compatibility 入口，不代表最终 Agent 架构。
- 历史 `backend/`、`clients/flutter/`、`frontend/` 和 `deploy/` 默认视为 legacy；未经用户明确要求不得扩展。
- Java/Python HTTP 链路当前不可用，不得顺手修复。
- 不得把未运行、未构建或未真实验收的能力写成 `DONE`。

## 开发前阅读顺序

实施当前 Phase 2C 前必须按顺序读取：

```text
AGENTS.md
→ health_agent/AGENTS.md
→ docs/architecture.md
→ docs/mvp-exec-plan.md
→ docs/decisions/0011-session-context-memory-boundaries.md
→ docs/implementation/phase-2c-interactive-session-cli.md
→ health_agent/README.md
```

如文档与代码冲突，先报告冲突，不得自行扩大范围或降低验收标准。

## 任务契约

开始修改前必须明确：

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
- 跨 legacy 运行时任务必须先定义接口、Schema 或 Tool Contract。
- 不允许无理由扩大任务范围。
- 不允许为了让测试通过而删除测试、放宽断言或绕过校验。
- 不允许主动新增生产依赖；确需新增时必须先说明理由、替代方案和影响。
- 不允许大规模重构，除非实施规范明确要求。
- 不允许把临时实现伪装成最终实现。

## Python Runtime 边界

Agent Runtime 负责：

- Session Message History。
- Model Turn。
- Tool Call Loop。
- 最大轮次、Tool 次数和超时。
- 错误收敛。
- Confirmation Pause/Resume 协议。
- lease、fence、checkpoint 和 recovery classification。
- Event/Trace。

Runtime 不负责：

- 健康业务事实。
- 训练规则、医学阈值或饮食判断。
- 直接访问数据库。
- 把 Conversation Summary 写成 UserProfile 或 HealthConstraint。
- 自动生成并生效长期 Memory。

Provider 只负责：

- 调用模型。
- 转换 system/user/assistant/tool 消息。
- 转换 Tool Schema。
- 解析 Assistant Response 与 Tool Calls。
- 归一化错误。
- 返回 usage 和 provider metadata。

Provider 不得知道 Program、Phase、WeeklyPlan、TodayAction、PlanVersion 或 HealthConstraint。

Tool Runtime 负责：

- ToolRegistry 白名单。
- ToolDefinition 模型可见合同。
- 参数、权限和副作用校验。
- ToolExecutor 确定性执行。
- 结构化 Tool Result 和错误。

当前正式 Tool 仍只允许只读或纯计算能力。

## Phase 2C 边界

Phase 2C 允许：

- 新增 `scripts/agent_chat.py`。
- 单进程复用同一 Runtime Components。
- 使用固定 `session_id` 连续调用 `GenericAgentLoop.run(...)`。
- 显式选择 memory/json Store。
- 显式恢复已有 Session。
- 最小命令：`/help`、`/new`、`/status`、`/resume`、`/exit`。
- 为上下文预算预留 Conversation Summary 边界。

Phase 2C 禁止：

- 把普通澄清问题建模为 PendingAction。
- 新增健康档案、训练计划或训练记录持久化。
- 新增数据库、Redis、FastAPI 或消息队列。
- 新增正式写操作 Tool。
- 新增 Safety Guard 半成品。
- 新增自动长期 Memory。
- 新增多 Agent、Sub-Agent、DAG 或工作流引擎。

## Session、Context、Memory 规则

```text
Session Message History ≠ 长期 Memory
Conversation Summary ≠ 已确认健康事实
UserProfile / HealthConstraint / Plan ≠ 模型记忆
Memory Candidate ≠ 自动生效的领域事实
```

- 普通 Clarification 通过下一轮 user message 继续。
- Proposal 是尚未执行的候选。
- Confirmation 只用于高影响写入或发布。
- 结构化健康事实必须由 Domain Service 与 Repository 管理。

## 修改原则

- 优先最小修改。
- 优先遵循现有结构，先搜索再决定是否新增文件。
- 优先补齐缺失点，不建立第二套重复 Contract。
- 遇到不确定信息时先搜索仓库，不允许凭经验猜测。
- 修改前检查工作区；不覆盖、不删除、不 stash 用户未提交修改。
- 不在仓库中写入真实健康资料、密钥、数据库密码、本机绝对路径或认证凭据。
- Trace 和日志不得记录完整健康原文、完整 Prompt、raw response、API Key 或认证信息。

## 禁止能力

未经独立阶段批准，不得新增：

- Shell Tool、任意文件系统 Tool、任意 SQL Tool。
- 写操作 Tool。
- 健康 Safety Guard 半成品。
- FastAPI、数据库、Redis、消息队列。
- 多 Agent、Sub-Agent、DAG 或工作流引擎。
- 普通文本伪 Tool Call 解析。
- Mock/Fake/Smoke 产品路径。

## 文档唯一事实来源

- 项目入口和当前摘要：`README.md`
- 产品范围：`docs/product-scope.md`
- 当前架构：`docs/architecture.md`
- 当前阶段与验收状态：`docs/mvp-exec-plan.md`
- 当前实施交接：`docs/implementation/phase-2c-interactive-session-cli.md`
- Python Runtime 入口和验证：`health_agent/README.md`
- 长期决策：`docs/decisions/`

历史文档与 legacy 代码不得被描述成当前可运行能力。

## 验证命令

仅执行与本次任务相关的命令，并如实报告未验证项。

```bash
cd health_agent
python3 -m compileall agent tests scripts
python3 -m unittest discover -s tests -v

cd ..
git diff --check
```

涉及 JSON Store、lease、checkpoint 或 recovery 时，还必须运行相应专项测试。

涉及真实连续对话时，必须执行 Phase 2C 实施规范中的真实 LLM 验收。

## 完成定义

完成报告必须包含：

- 修改、新增和删除文件。
- 实际执行的验证命令与结果。
- 当前 Session 是否连续或跨进程恢复。
- 真实模型回合数和工具调用次数。
- 是否经过 `INITIAL_PLANNING`。
- 当前环境无法验证的内容。
- 未完成事项和风险。
- 是否越过原任务边界。
