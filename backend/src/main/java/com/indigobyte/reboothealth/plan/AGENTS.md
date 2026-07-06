# Plan 模块规则

## 职责

本模块维护长期 Plan 身份、7 天 PlanVersion、PlanDay、PlanItem、确认、取消、复制、快照和当前计划查询。

## 不变量

- Plan 是长期身份；周期内容由 PlanVersion 表达。
- PlanVersion 周期固定 7 天。
- 已确认、已替代和已取消版本不可原地编辑。
- 当前计划按用户时区和日期查询，不维护全局 `ACTIVE` 状态。
- 同周期修订确认后替代旧确认版本；不同确认周期不得重叠。
- 确认时保存目标和健康约束稳定快照。
- `confirm`、`cancel` 和草案编辑必须校验 revision。
- 关键 POST 必须幂等，重放不得重复状态转换或审计。

## AI 边界

- AI 只能提出或生成草案，不得直接确认、发布或原地修改生效计划。
- Python 不直接调用 Repository 或 Mapper。
- M2.5-B 只能通过受控 Java Command 将用户确认后的候选映射到现有计划引擎。
- 不得为 AI 另建一套并行 WeeklyPlan 事实来源。

## 禁止

- 不因 Program、Phase 或 DailyAction 需求推翻 M2B 版本模型。
- 不在本模块实现执行记录、Observation、周分析或模型 Prompt。
- 不把内部 UUID、revision、状态枚举设计成用户必须理解的产品概念。

## 验证

必须覆盖状态机、revision 冲突、日期边界、快照稳定性、周期重叠、幂等重放和审计。