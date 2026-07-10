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

## 当前阶段约束

- 产品运行 Provider 为 OpenAI-compatible `ModelProvider.complete_turn(...)`。
- 产品 LLM 配置使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`；Bootstrap 从 `health_agent/.env` 加载，shell 环境变量优先。
- `INITIAL_PLANNING` 仍是临时兼容业务入口，不代表最终 Agent 架构。
- 完整 Tool Call Loop、FastAPI 产品 API、数据库、Memory、完整 Safety、Confirmation Resume、Plan 发布和 DailyRecord 尚未实现。
- 历史 `backend/`、`clients/flutter/`、`frontend/`、`deploy/` 代码仍在仓库中，但默认只视为 legacy；未经用户明确要求不得扩展其业务能力。
- Java/Python HTTP 链路当前不可用，不得在未获授权时顺手修复。
- 不得把未运行、未构建、未人工验收的能力写成 `DONE`。

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
- 跨旧运行时任务必须先定义接口、Schema 或 Tool Contract，再分别实施。
- 不允许在没有说明理由的情况下扩大任务范围。
- 不允许为了让测试通过而降低业务规则、删除测试、放宽断言或绕过校验。
- 不允许主动新增生产依赖；确需新增时，必须先说明原因、替代方案和影响范围。
- 不允许大规模重构，除非用户明确要求。
- 不允许把临时实现伪装成最终实现。

## Python Runtime 边界

Agent Runtime 只负责：

- Session。
- Model Turn。
- Tool Call Loop。
- 最大轮次。
- 超时。
- 错误收敛。
- Confirmation Pause 状态协议。
- Event/Trace。

Provider 只负责：

- 调用模型。
- 转换消息。
- 转换 Tool Schema。
- 解析 Assistant Response。
- 解析 Tool Calls。
- 归一化错误。
- 返回 Usage 和 Provider Metadata。

Provider 不得知道 Program、Phase、WeeklyPlan、TodayAction、PlanVersion 或 HealthConstraint。

测试替身只能放在 `health_agent/tests/`，不得被产品 Bootstrap 引用。

## 修改原则

- 优先最小修改。
- 优先遵循现有结构。
- 优先补齐缺失点，不重写已有模块。
- 遇到不确定信息时，先在仓库中搜索，不允许凭经验猜测。
- 如果发现规则冲突，必须暂停并说明冲突点。
- 修改前检查工作区；不覆盖、不删除、不 stash 用户未提交修改。
- 不在仓库中写入真实健康资料、密钥、数据库密码、本机绝对路径或完整认证凭据。
- Trace 和日志不得记录完整健康原文、完整 prompt、raw model response、API key 或认证信息。

## 文档唯一事实来源

- 项目入口和当前真实状态：`README.md`
- Python Runtime 入口和验证：`health_agent/README.md`
- 历史产品、架构、领域和阶段文档：`docs/`

历史 `docs/` 中仍可能存在 Java 分层旧口径。未被本轮任务触及的历史文档不得被改写成已完成迁移。

## 验证命令

仅执行与本次任务相关的命令，并如实报告未验证项。

```bash
# Python
cd health_agent
python3 -m compileall agent tests
python3 -m unittest discover -s tests

# 文档/通用
git diff --check
```

涉及旧目录时再按对应目录规则读取下级 `AGENTS.md` 并执行相应验证。

## 完成定义

完成报告必须包含：

- 修改、新增和删除文件；
- 实际执行的验证命令与结果；
- 当前环境无法验证的内容；
- 未完成事项和风险；
- 是否越过原任务边界。
