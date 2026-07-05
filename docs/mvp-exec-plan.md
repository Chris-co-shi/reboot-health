# MVP 执行计划

本文档是持续更新的执行计划。每个里程碑完成后必须更新状态、验收结果、测试结果和下一步。

## 1. 状态约定

- `TODO`：未开始。
- `IN_PROGRESS`：进行中。
- `DONE`：已完成并通过验收。
- `BLOCKED`：被未确认事项或外部条件阻塞。

## 2. 当前总状态

- 当前阶段：M2A。
- 当前目标：用户档案、健康约束、目标管理。
- 当前业务状态：M2A 本地实现已完成，等待用户人工验收。
- 下一阶段：M2B 计划、计划版本和人工确认。

## 3. 里程碑

### M1 文档和工程骨架

状态：DONE

范围：

- 项目规则文档。
- 产品、领域、架构、AI、安全规则和执行计划文档。
- 后端空骨架。
- 前端空骨架。
- Docker Compose 配置。

验收条件：

- 后端测试通过。
- 前端类型检查和构建通过。
- Docker Compose 配置可校验。

### M2A 用户档案、健康约束、目标管理

状态：IN_PROGRESS，待用户验收后改为 DONE

范围：

- 唯一 `UserProfile`。
- `HealthConstraint` 创建、编辑、状态变更、归档。
- `Goal` 创建、编辑、状态变更、归档。
- M2A 审计追加写。
- `/plan/setup/profile`、`/plan/setup/constraints`、`/plan/setup/goals`。
- README 小范围更新。

不包含：

- AI 调用。
- AI 计划生成。
- Plan 和 PlanVersion。
- 今日执行。
- 周分析。
- 规则引擎。
- 登录注册。
- 多用户。
- 文件上传。
- 复杂动作库。

验收条件：

- 可首次创建并更新唯一 `UserProfile`。
- `UserProfile` 不含 `currentWeightKg`，使用 `baselineWeightKg`。
- 可创建、编辑、状态切换、归档 `HealthConstraint`。
- `HealthConstraint` 状态机符合领域文档。
- 可创建、编辑、状态切换、归档 `Goal`。
- `Goal` 状态机符合领域文档。
- 归档不物理删除，归档后不可普通编辑。
- 所有业务修改同事务写入审计。
- 查询不写审计。
- `PUT /api/v1/profile` 幂等请求不重复写业务记录，默认不写 `NO_CHANGE` 审计。

测试要求：

- UserProfile 首次保存创建。
- UserProfile 再次保存更新同一条。
- UserProfile 完全相同请求不重复更新、不写审计。
- 单档案唯一性约束。
- HealthConstraint 创建、修改、状态变化、归档。
- HealthConstraint 非法状态流转拒绝。
- HealthConstraint 已归档后禁止编辑和状态变更。
- Goal 创建、修改、状态变化、归档。
- Goal 非法状态流转拒绝。
- Goal 已归档后禁止编辑和状态变更。
- Goal 单位和值组合校验。
- API 集成测试覆盖关键路径和错误路径。
- Flyway 在 Testcontainers PostgreSQL 上完整执行。
- `pnpm run typecheck`。
- `pnpm run build`。

当前验证结果：

- `/Users/sxc/Documents/tool/apache-maven-3.9.0/bin/mvn test`：通过，21 个后端测试。
- `pnpm run typecheck`：通过。
- `pnpm run build`：通过；Vite 输出依赖注释和大 chunk 警告，不影响构建。
- `docker compose -f deploy/docker-compose.yml config`：通过。

OPEN：

- OPEN: `goalType = OTHER` 且 `unit = NONE` 时是否允许只填写文字目标说明。
- OPEN: `HealthConstraint.bodyRegion` 是否需要支持多选；M2A 默认单选。
- OPEN: 是否在 M2A API 中提供审计查询；默认只写入。
- OPEN: 是否将 `displayName` 默认填充为固定昵称；默认不自动填。
- OPEN: 是否在 M2A 前端显示 `RESOLVED` 项；默认在非归档列表中显示，并明确标记“已解决”。

### M2B 计划、计划版本和人工确认

状态：TODO

范围：

- 手工创建计划草案。
- 用户确认后生成 `ACTIVE` 计划版本。
- 计划版本不可原地修改。

### M3 今日执行和每日数据记录

状态：TODO

范围：

- 今日页读取当前计划版本。
- 每日任务完成状态。
- 训练、身体指标、症状和饮食执行记录。
- `BodyMetricEntry` 提供后续“当前体重”的事实来源。

### M4 周分析和确定性规则

状态：TODO

范围：

- 生成 7 天周分析。
- 实现疼痛、睡眠、游泳呛水、完成率、血压提醒等确定性规则。

### M5 AI 起草及调整建议

状态：TODO

范围：

- OpenAI 兼容接口调用。
- 结构化 JSON 输出。
- JSON Schema 校验。
- 语义校验。
- 规则后置校验。

### M6 调整确认和新计划版本

状态：TODO

范围：

- 全部接受。
- 部分接受。
- 全部拒绝。
- 接受项生成新计划版本。
- 审计记录。

### M7 部署、备份和个人验收

状态：TODO

范围：

- Windows 10 + Docker 部署说明。
- Tailscale 访问说明。
- 本地数据导出或备份。
- 端到端人工验收。
