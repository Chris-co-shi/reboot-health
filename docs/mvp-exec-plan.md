# MVP 执行计划

本文档是唯一里程碑状态来源。每个里程碑完成后必须更新状态、验收结果、测试结果和下一步。

## 1. 状态约定

- `TODO`：未开始。
- `IN_PROGRESS`：进行中。
- `CODE_ACCEPTED`：自动化代码验收通过，等待用户页面人工验收。
- `DONE`：用户验收通过。
- `BLOCKED`：被未确认事项或外部条件阻塞。

## 2. 当前总状态

- 当前阶段：M2.5-A。
- 当前目标：Flutter 主客户端骨架、AgentRun 技术链路、Python Agent Runtime Model Mock、设备 bootstrap/配对/凭据和安全审计。
- 当前业务状态：M2A、M2B 已完成功能验收；M2.5-A 实施后等待用户技术链路人工验收。
- 下一阶段：M2.5-B AI 首次规划闭环。

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

状态：DONE

范围：

- 唯一长期 Plan。
- 手工创建 7 天计划草案。
- 从 `CONFIRMED` 或 `SUPERSEDED` 版本复制创建新草案。
- 草案预览、确认和取消。
- `DRAFT`、`CONFIRMED`、`SUPERSEDED`、`CANCELLED` 状态。
- 当前计划按日期查询 `CONFIRMED` 版本。
- 版本历史。
- Goal 关联、确认时目标摘要快照和 ACTIVE 健康约束稳定快照。
- `revision` 并发控制。
- 必须 POST 接口的 `Idempotency-Key` 幂等控制。
- M2B 审计追加写。
- `confirm`、`cancel`、删除计划日、删除计划条目均校验 `expectedRevision`。
- 当前计划日期按 `UserProfile.timezone` 或显式 `app.default-timezone` 计算。

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
- stale revision、跨 UTC 日期、preview、历史快照、V5 数据库约束和扩展 PlanItemType 均有自动化测试覆盖。

页面人工验收清单：

- 创建唯一长期 Plan。
- 创建 7 天草案并编辑计划日。
- 为计划日添加、编辑和删除条目。
- 预览并确认计划。
- 提前确认未来周期计划。
- 从已确认版本复制新周期草案。
- 同周期修订确认后旧版本显示为已替代。
- 双击确认不会重复确认或重复审计。
- 模拟网络失败、408、429 或 5xx 后重试不会生成第二个业务结果。
- 已确认历史详情展示确认时健康约束和目标摘要，不受后续修改影响。
- `CARDIO`、`NUTRITION`、`MEASUREMENT` 类型能正常显示中文并刷新后保留。
- 刷新页面后版本历史和详情仍存在。

### M2.5-A 技术与产品骨架

状态：IMPLEMENTED_WITH_BLOCKERS

范围：

- Flutter iOS、Android、macOS、Windows 主客户端最小骨架。
- Flutter 调用 Java 后端，不直接调用 Python。
- Java 创建并管理 `AgentRun`。
- Java 在短事务创建 `AgentRun` 后异步调用 Python Agent Runtime。
- Python 默认使用稳定 Model Mock 返回结构化结果。
- Java 校验结构化结果并保存到 `AgentRun`。
- Flutter 教练页展示 AgentRun 状态和结构化卡片。
- 首台设备 bootstrap 初始化。
- 后续设备配对。
- 独立设备凭据和设备撤销。
- 安全审计。

不包含：

- AI 首次规划访谈。
- Goal 开放模型改造。
- HealthConstraint 候选。
- Program、Phase、WeeklyPlan 生成。
- DailyAction、DailyActionExecution。
- Observation。
- HealthKit / Health Connect。
- 真实云模型供应商接入。
- Vue 新业务页面。

自动化验证：

- 后端 Maven 测试通过。
- Python Runtime 单元测试通过。
- Flutter `flutter analyze`、`flutter test` 和四端 debug build 需在具备 Flutter SDK 的环境中执行；当前本机 `flutter` 命令不可用，尚未验证。
- Docker Compose 配置可校验。
- `git diff --check` 通过。

当前阻塞：

- 当前环境缺少 Flutter SDK，无法执行 `flutter create` 生成真实四端 runner，也无法验证 `flutter_secure_storage` 四端插件兼容性和四端 debug build。

人工验收清单：

- 通过服务端 CLI 生成 bootstrap code。
- Flutter 输入 bootstrap code 初始化首台设备。
- 错误、过期或已消费 code 被拒绝。
- 初始化后不能再次初始化首台设备。
- 已授权设备创建配对码。
- 新设备通过配对码完成配对。
- 撤销某台设备不影响其他设备。
- 教练页点击“检查AI教练连接”后展示运行中、完成或失败状态。
- 结构化卡片显示“AI教练服务已连接”。
- 普通用户页面不展示 UUID、内部状态码或技术堆栈；开发调试信息必须折叠隔离。

### M2.5-B AI 首次规划闭环

状态：TODO

范围：

- 自然语言访谈。
- AI 理解候选卡片。
- 用户纠正和确认。
- Goal 开放表达能力演进，但 Goal 仍是唯一事实来源。
- HealthConstraint 候选确认，并保留开放表达字段。
- Program 草案。
- Phase 草案。
- 首周 WeeklyPlan 草案。
- 安全检查。
- 用户确认后发布现有 PlanVersion。

### M2.5-C 最小今日执行反馈

状态：TODO

范围：

- 今日行动卡。
- 完成、部分完成、跳过。
- 最小 `DailyActionExecution`。
- 训练结束一次简短反馈。
- Agent 记忆候选。
- 用户查看和纠正 AI 理解。

不包含：

- 完整 Observation。
- 周分析。
- 设备同步。
- 训练播放器。

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
- OPEN: 云模型具体供应商和模型。
- OPEN: 月度成本上限。
- OPEN: 模型调用数据保留周期。
- OPEN: 提醒静默时段和主动询问次数上限。
- OPEN: HealthKit 和 Health Connect 插件选择。
- OPEN: bootstrap code 的有效时长、字符格式和失败次数限制配置值。
