# MVP 执行计划

本文档是唯一里程碑状态来源。每个里程碑完成后必须更新状态、验收结果、测试结果和下一步。

## 1. 状态约定

- `TODO`：未开始。
- `IN_PROGRESS`：进行中。
- `CODE_ACCEPTED`：自动化代码验收通过，等待用户页面人工验收。
- `DONE`：用户验收通过。
- `BLOCKED`：被未确认事项或外部条件阻塞。

## 2. 当前总状态

- 当前阶段：M2B。
- 当前目标：计划群组、计划版本、人工确认、复制草案和幂等 POST。
- 当前业务状态：M2A 已完成功能验收；M2B 代码验收通过后等待用户页面人工验收。
- 下一阶段：M3 今日执行和每日数据记录。

## 3. 里程碑

### M1 文档和工程骨架

状态：DONE

范围：

- 项目规则文档。
- 产品、领域、架构、AI、安全规则和执行计划文档。
- 后端空骨架。
- 前端空骨架。
- Docker Compose 配置。

### M2A 用户档案、健康约束、目标管理

状态：DONE

范围：

- 唯一 `UserProfile`。
- `HealthConstraint` 创建、编辑、停用、解决、归档。
- `Goal` 创建、编辑、暂停、恢复、完成、取消、归档。
- M2A 审计追加写。
- `/plan/setup/profile`、`/plan/setup/constraints`、`/plan/setup/goals`。

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

M2A-FIX 验收要求：

- 普通状态接口不能归档。
- 专用归档接口要求原因、设置 `archivedAt`、写入归档审计。
- Goal 只有 `ACTIVE` 和 `PAUSED` 可编辑。
- Goal 单位和值规则符合领域模型。
- Persistence DO 与领域聚合分离。
- Repository Port 显式区分 `insert` 和 `update`。
- V2 Flyway 约束通过 PostgreSQL Testcontainers。
- 前端显示中文枚举标签，提交前执行表单校验。
- 文档和测试脱敏。

自动化验证：

- 后端测试通过。
- 前端 `pnpm install --frozen-lockfile`、`typecheck`、`build` 通过。
- Docker Compose 配置可校验。
- `git diff --check` 通过。
- 隐私和架构搜索检查通过。

页面人工验收完成前，M2A 只能记录为：

> 代码验收通过，等待用户页面人工验收

用户页面人工验收清单：

- 创建和更新个人档案。
- 创建、编辑、停用、解决和归档健康约束。
- 创建、暂停、恢复、完成、取消和归档目标。
- 验证终态目标不能编辑。
- 验证内部枚举均显示为中文。
- 验证刷新页面后数据存在。

### M2B 计划、计划版本和人工确认

状态：CODE_ACCEPTED

范围：

- 唯一长期 Plan。
- 手工创建 7 天计划草案。
- 从 `CONFIRMED` 或 `SUPERSEDED` 版本复制创建新草案。
- 草案预览、确认和取消。
- `DRAFT`、`CONFIRMED`、`SUPERSEDED`、`CANCELLED` 状态。
- 当前计划按日期查询 `CONFIRMED` 版本。
- 版本历史。
- Goal 关联和确认时 ACTIVE 健康约束快照。
- `revision` 并发控制。
- 必须 POST 接口的 `Idempotency-Key` 幂等控制。
- M2B 审计追加写。

不包含：

- AI。
- 今日执行。
- 每日指标记录。
- 周分析。
- 规则引擎。
- 登录或多用户。
- 通知。
- 复杂动作库。

自动化验证：

- 后端测试通过。
- 前端 `pnpm install --frozen-lockfile`、`typecheck`、`build` 通过。
- Docker Compose 配置可校验。
- `git diff --check` 通过。

页面人工验收清单：

- 创建唯一长期 Plan。
- 创建 7 天草案并编辑计划日。
- 为计划日添加、编辑和删除条目。
- 预览并确认计划。
- 提前确认未来周期计划。
- 从已确认版本复制新周期草案。
- 同周期修订确认后旧版本显示为已替代。
- 双击确认不会重复确认或重复审计。
- 刷新页面后版本历史和详情仍存在。

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

- 私有部署说明。
- Tailscale 访问说明。
- 本地数据导出或备份。
- 端到端人工验收。

## 4. OPEN

- OPEN: `HealthConstraint.bodyRegion` 是否需要支持多选；M2A 默认单选。
- OPEN: 是否在 M2A API 中提供审计查询；默认只写入。
- OPEN: 是否将 `displayName` 默认填充为固定昵称；默认不自动填。
- OPEN: 是否在 M2A 前端显示 `RESOLVED` 项；默认在非归档列表中显示，并明确标记“已解决”。
