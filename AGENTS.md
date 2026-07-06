# 仓库级 Agent 规则

## 适用范围与优先级

本文件适用于整个仓库。修改目录时，还必须读取离目标文件最近的 `AGENTS.md`：

- Java：`backend/AGENTS.md`
- Python Health Agent Harness：`agent-runtime/AGENTS.md`
- Flutter：`clients/flutter/AGENTS.md`
- 冻结 Vue 工具：`frontend/AGENTS.md`
- 部署：`deploy/AGENTS.md`
- 文档：`docs/AGENTS.md`
- Java 业务模块：对应包目录下的 `AGENTS.md`

用户当前任务中的直接要求优先；下级规则只能收紧边界，不能放宽本文件的安全和范围约束。

## 项目核心定位

`reboot-health` 不是“Java 健康后台加一个 AI 接口”，而是一个由领域型 Agent Harness 驱动的 AI-native 个人健康系统。

核心架构身份：

- **Python Health Agent Harness**：产品智能与任务编排核心。
- **Java Health Domain Kernel**：已确认事实、确定性安全规则、权限、确认、审计、幂等和领域状态权威。
- **Flutter Client**：正式用户交互与多平台体验。
- **Vue Debug Tool**：冻结的内部调试工具。

关键原则：

> Python 决定下一步应该做什么；Java 决定什么允许做并可靠保存；Flutter 负责用户如何表达、确认和行动。

Python 是智能控制流核心，但不是业务事实权威。Java 是可信领域内核，但不是产品智能编排核心。

## 产品方向

- AI 从首次使用开始主动理解、澄清、规划、调用受控工具、解释和复盘。
- 用户主要负责自然表达、纠正、确认和执行反馈，不维护技术字段。
- Agent 通过 Skills、Tools、Memory、Approval、Trace 和 Evaluation 驱动业务闭环。
- Java 通过领域不变量和确定性规则限制 Agent 能做什么。
- Flutter 采用自然语言与页面卡片结合的正式体验。
- 本项目不做医学诊断，不替代医生意见。

## Harness Engineering 原则

Python Health Agent Harness 的长期能力边界包括：

- Agent Loop：有限轮次的任务决策和工具调用循环。
- Skill Registry：按场景加载可测试、可版本化的领域 Skill。
- Tool Registry：调用 Java 提供的受控领域工具。
- Session Runtime：区分 Conversation、Session、AgentRun、ToolCall 和 Confirmation。
- Context Builder：按任务组装最小必要上下文。
- Memory Manager：管理事实候选、行为模式和策略经验。
- Approval Coordinator：决定自动执行、等待确认或阻断。
- Model Router：支持 Mock、云模型和未来本地模型切换。
- Run Trace：记录 Skill、上下文摘要、工具调用、策略判断和失败归因。
- Evaluation：以固定场景验证 Harness 改动是否提高可靠性。
- Recovery：支持超时、取消、恢复和有限重试。

不得将 Harness Engineering 简化为一个大 Prompt 或一次模型调用，也不得直接复制 Hermes 的开放 Shell、任意文件系统工具或通用自治能力。

## 任务契约

开始修改前，必须在计划中明确：

```text
Primary Module:
Allowed Paths:
Forbidden Paths:
Required Verification:
Out of Scope:
```

规则：

- 每个任务只能有一个主模块。
- 默认只修改一个运行时；跨运行时任务必须先定义接口、Schema 或 Tool Contract，再分别实施。
- 同一任务不得同时新增 Java、Python、Flutter 和 Vue 业务能力。
- Harness 功能优先在 Python 中设计；领域事实和安全工具在 Java 中实现；交互在 Flutter 中实现。
- 集成任务只能连接已完成能力，不能顺带增加新产品需求。
- 发现任务超出声明路径时停止并报告，不自行扩大范围。

## 当前阶段约束

- M2.5-A 当前为 `IMPLEMENTED_WITH_BLOCKERS`，Flutter SDK 和四端构建尚未验证。
- 当前 Python Runtime 仍是 Model Mock 技术骨架，不得声称已经完成真正的 Agent Harness。
- 未经用户明确要求，不进入 M2.5-B 或 M2.5-C。
- 不得把未运行、未构建、未人工验收的能力写成 `DONE`。
- 不得为了“完整”提前实现 HealthKit、Health Connect、真实模型、多 Agent、消息队列或向量数据库。

## 通用工作规则

- 所有计划、说明、自查和验收报告使用中文。
- 代码标识符、类名、方法名和字段名使用英文。
- 修改前检查工作区；不覆盖、不删除、不 stash 用户未提交修改。
- 不为了测试通过而删除测试、放宽断言、绕过校验或降低业务不变量。
- 新增生产依赖前说明必要性、替代方案和影响范围。
- 不在仓库中写入真实健康资料、密钥、数据库密码、本机绝对路径或完整认证凭据。
- 关键状态转换必须可审计、可测试、可恢复。

## 跨模块权威边界

- Flutter 只调用 Java 对外 API，不直接调用 Python。
- Python 通过受控 Tool Contract 使用 Java 能力，不连接 PostgreSQL，不直接修改业务事实。
- Java 保存已确认事实并执行确定性安全规则，不负责 Skill 选择、Prompt 编排和智能控制流。
- AI 输出是候选，不是领域事实。
- 计划、健康约束和重要目标变化必须遵守确认边界。
- 低风险自动调整只能降低风险或复杂度，必须可解释、可撤销、可审计。
- Agent 工具必须声明权限、影响等级、确认策略、幂等策略、超时和审计策略。

## 验证命令

仅执行与本次任务相关的命令，并如实报告未验证项。

```bash
# Java
cd backend && mvn test

# Python
cd agent-runtime
python3 -m compileall agent_runtime tests
python3 -m unittest discover -s tests

# Flutter
cd clients/flutter
flutter pub get
flutter analyze
flutter test

# 冻结 Vue，仅在修改 frontend 时
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build

# 部署
cd ../..
docker compose -f deploy/docker-compose.yml config

git diff --check
```

没有对应 SDK 或平台时，标记为“未验证”，不得宣称通过。

## 文档唯一事实来源

- 产品定位、体验、范围：`docs/product-scope.md`
- 组件、职责、调用和信任边界：`docs/architecture.md`
- 业务聚合与不变量：`docs/domain-model.md`
- 已实现 API、数据库、错误码：`docs/api-db.md`
- 健康和系统安全规则：`docs/safety-rules.md`
- 当前阶段与交付状态：`docs/mvp-exec-plan.md`
- 已确认重大决策：`docs/decisions/`
- 项目入口和工程卖点：`README.md`

同一事实只能在一个权威文档中完整描述，其他位置使用链接或一句摘要。

## 完成定义

完成报告必须包含：

- 修改、新增和删除文件；
- 实际执行的验证命令与结果；
- 当前环境无法验证的内容；
- 未完成事项和风险；
- 是否越过原任务边界。

每个里程碑完成后停止，等待用户验收。