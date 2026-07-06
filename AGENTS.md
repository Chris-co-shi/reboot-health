# 仓库级 Agent 规则

## 适用范围与优先级

本文件适用于整个仓库。修改目录时，还必须读取离目标文件最近的 `AGENTS.md`：

- Java：`backend/AGENTS.md`
- Python Runtime：`agent-runtime/AGENTS.md`
- Flutter：`clients/flutter/AGENTS.md`
- 冻结 Vue 工具：`frontend/AGENTS.md`
- 部署：`deploy/AGENTS.md`
- 文档：`docs/AGENTS.md`
- Java 业务模块：对应包目录下的 `AGENTS.md`

用户当前任务中的直接要求优先；下级规则只能收紧边界，不能放宽本文件的安全和范围约束。

## 产品方向

`reboot-health` 是 AI-first 的个人健康、减脂和规律训练辅助系统：

- AI 主动理解、生成候选和解释。
- Java 保存事实、执行确定性安全规则、管理确认和状态。
- Python 负责模型调用、编排和结构化候选输出。
- Flutter 是正式用户客户端。
- Vue 仅是冻结的内部调试工具。
- 用户主要负责表达、纠正、确认和执行反馈，不维护技术字段。

本项目不做医学诊断，不替代医生意见。

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
- 默认只修改一个运行时；跨运行时任务必须先定义接口或 Schema，再分别实施。
- 同一任务不得同时新增 Java、Python、Flutter 和 Vue 业务能力。
- 集成任务只能连接已完成能力，不能顺带增加新产品需求。
- 发现任务超出声明路径时停止并报告，不自行扩大范围。

## 当前阶段约束

- M2.5-A 当前为 `IMPLEMENTED_WITH_BLOCKERS`，Flutter SDK 和四端构建尚未验证。
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

- Flutter 只调用 Java API，不直接调用 Python。
- Python 不连接 PostgreSQL，不直接修改业务事实，不发布计划。
- Java 不负责页面展示策略，也不在领域事务中执行模型远程调用。
- AI 输出是候选，不是领域事实。
- 计划、健康约束和重要目标变化必须遵守确认边界。
- 低风险自动调整只能降低风险或复杂度，必须可解释、可撤销、可审计。

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
- 项目入口：`README.md`

同一事实只能在一个权威文档中完整描述，其他位置使用链接或一句摘要。

## 完成定义

完成报告必须包含：

- 修改、新增和删除文件；
- 实际执行的验证命令与结果；
- 当前环境无法验证的内容；
- 未完成事项和风险；
- 是否越过原任务边界。

每个里程碑完成后停止，等待用户验收。