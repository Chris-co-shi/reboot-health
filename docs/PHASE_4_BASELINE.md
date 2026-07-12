# Phase 4 产品与领域重基线

## 1. 文档状态

状态：`DISCOVERY_BASELINE`

生效日期：2026-07-12

本文件记录已经由用户确认的 Phase 4 产品范围、领域边界和验收方向。它用于约束后续讨论、ADR、详细设计和 implementation specification，但不代表 Phase 4 已进入代码实施。

在满足以下条件前，Phase 4 不得标记为 `READY`：

1. Phase 3 的生产基础、Identity、用户归属授权、服务间授权和安全验收完成。
2. Phase 4 各 Slice 的领域合同、状态机、API、迁移和验收被逐项批准。
3. 医学风险阈值完成专业审核，或明确标记为不允许实施的 `NEEDS_MEDICAL_REVIEW`。
4. 营养数据源、许可证和归一化策略完成技术与合规 Spike。

## 2. 阶段边界

### 2.1 Phase 3

Phase 3 负责生产技术与权限底座：

- Health Platform 生产基础与 PostgreSQL 持久化。
- Identity、登录、OAuth/OIDC、Session、MFA 和账号生命周期。
- `USER`、`ADMIN_OPERATOR` 和服务主体权限边界。
- 所有业务资源的 `userId` 归属授权。
- Health Platform 与 health-agent 的 mTLS、短期 JWT 和 Tool Scope。
- health-agent 的生产 Task/Run/API/Worker、lease、fence、checkpoint 和恢复能力。
- 跨用户、跨任务、Token 重放、Secret、日志脱敏和故障恢复验收。

Phase 3 不负责训练、恢复、饮食计划及其执行反馈业务。

### 2.2 Phase 4

Phase 4 负责第一个完整健康业务闭环：

```text
自然语言表达目标
→ 动态采集和补充关键信息
→ FactCandidate / GoalCandidate
→ 用户分级确认
→ 综合 HealthProgram 候选
→ 分领域查看
→ 用户整体确认 ProgramVersion
→ 执行训练、恢复和饮食任务
→ 事件反馈、每日 Check-in、周期复盘
→ 偏差和风险评估
→ AdjustmentCandidate
→ 用户确认新的 ProgramVersion
```

## 3. 首发产品入口

Phase 4 首个验证客户端为独立 Web 用户端：

```text
clients/web/        # 普通用户业务入口，Phase 4 规划目录
frontend/           # Vue 3 管理、运维、诊断和审计端
clients/miniapp/    # 后续用户客户端
clients/flutter/    # 后续用户客户端
```

原则：

- `frontend/` 不得同时承担普通用户健康业务与管理端职责。
- Web 用户端只调用 Health Platform。
- 微信小程序与 Flutter 复用相同的 Health Platform API 和领域合同，在 Web 闭环稳定后接入。
- 客户端不得直接访问 health-agent、数据库、Redis、MinIO 或内部 Tool handler。

## 4. Phase 4 产品范围

Phase 4 同时包含：

1. 训练计划。
2. 恢复计划。
3. 完整的普通人群饮食计划。

完整饮食计划包括热量与宏量营养目标、餐次安排、食物选择与替换、执行记录和动态调整，但不包含疾病治疗性医学营养、诊断、处方或替代营养师/医生的服务。

以下情况必须限制、暂停或转介专业人员，不得由普通 Agent 自主制定治疗性方案：

- 需要医学营养治疗的疾病。
- 严重肝、肾、心血管或代谢疾病。
- 进食障碍风险。
- 孕期、哺乳期等特殊状态。
- 严重过敏或无法确认的药物—食物相互作用。
- 极端能量限制或其他高风险目标。

## 5. 综合计划模型

### 5.1 聚合关系

```text
HealthProgram
├── ProgramCycle
├── ProgramVersion
│   ├── TrainingPlanVersion
│   ├── RecoveryPlanVersion
│   └── NutritionPlanVersion
├── GoalSnapshot
├── FactSnapshot
├── RiskSnapshot
└── ProgressionPolicy
```

三个子计划独立版本化，`ProgramVersion` 保存当前一致组合的版本引用。

示例：

```text
ProgramVersion 3
├── TrainingPlanVersion 4
├── RecoveryPlanVersion 2
└── NutritionPlanVersion 5
```

用户最终确认的是完整 `ProgramVersion`，不是三个互不关联的计划。

### 5.2 不变量

- 一个 `HealthProgram` 同一时刻最多存在一个当前生效版本。
- Agent 只能创建候选，不能确认或发布正式计划。
- 新候选未确认前，旧的当前版本继续有效。
- 已确认版本不得原地覆盖。
- 已完成的执行记录不得因计划修订而改变。
- 调整只作用于尚未完成的未来安排。
- 跨领域变化必须重新执行一致性检查。
- 关键事实变化可以使候选失效，但不得静默修改历史。

## 6. 时间结构与滚动计划

计划采用：

```text
ProgramCycle
→ ProgramPhase
→ WeekPlan
→ DailySchedule
```

生成策略：

- 生成完整周期框架，首版默认支持约 8–12 周的中期路线。
- 详细生成近期 WeekPlan，首版目标窗口为未来两周。
- 详细生成 DailySchedule，首版目标窗口为未来七天。
- 根据执行、反馈和风险滚动生成后续安排。
- 已执行和历史已确认内容不得被滚动窗口重写。

具体默认周期和窗口属于后续详细设计配置，不应硬编码为不可变业务规则。

## 7. 对话式信息采集

首次采集采用纯对话，不提供传统必填问卷作为主流程。

```text
用户自然描述
→ Agent 提取候选事实和目标
→ 确定性 ReadinessPolicy 判断缺失、冲突和风险
→ Agent 只追问当前必要信息
→ 用户确认
```

系统内部必须维护结构化就绪状态：

- `TRAINING_READY`
- `RECOVERY_READY`
- `NUTRITION_READY`
- `PROGRAM_READY`

缺少阻断型关键信息时不得生成可确认的综合计划。

### 7.1 事实来源

必须区分：

- 用户明确陈述。
- 用户确认的系统计算结果。
- Agent 推测。
- 文件或外部数据候选。
- 未知信息。

Agent 推测不得伪装成用户事实。

### 7.2 分级确认

- 普通、低影响事实在一个对话阶段结束时批量确认。
- 疾病、疼痛、损伤、药物、食物过敏、关键身体指标和目标数值等高影响事实单独确认。
- 模型推测必须明确询问，不得默认转为正式事实。
- 用户已明确表达且无歧义的信息不应被机械地重复追问。
- 文件提取的健康字段仍遵守逐项确认要求。

## 8. 候选计划查看与修改

用户按领域查看：

1. 周期、综合目标和阶段。
2. 训练计划。
3. 恢复计划。
4. 饮食计划。
5. 关键风险、约束、数据来源和不确定性。

最终通过一次明确操作整体确认 `ProgramVersion`。

修改分两类：

- 低风险、等价、确定性可验证的轻量修改，可以直接作用于未完成部分并保留 Revision。
- 训练负荷、热量目标、阶段结构、安全限制等实质性修改，必须重新评估并生成候选版本。

## 9. 执行记录与反馈

### 9.1 默认轻量记录

训练：

- 完成、部分完成、跳过或中止。
- 实际强度和异常。
- 疼痛或不适。
- 可选展开记录每组重量、次数和 RPE。

恢复：

- 睡眠时长与质量。
- 疲劳、酸痛、压力和精神状态。
- 恢复任务完成情况。

饮食：

- 餐次完成度和主要偏差。
- 饥饿感、饱腹感和异常反应。
- 可选展开记录食物、份量和营养数据。

### 9.2 反馈节奏

- 任务或训练后的事件反馈。
- 低负担每日 Check-in。
- 周期性综合复盘，首版以周复盘为默认方向。
- 疼痛、异常疲劳、连续未完成或趋势异常时即时追问，不等待周期结束。

## 10. 调整语义

调整可以由以下事件触发：

- 用户主动请求。
- 周期复盘。
- 连续执行偏差。
- 疲劳、疼痛或睡眠异常。
- 体重、围度或其他目标趋势偏离。
- 阶段结束。
- 关键健康事实变化。
- 滚动详细计划窗口即将结束。

系统自动评估影响范围，但只创建 `AdjustmentCandidate`。未经用户确认，不得让新的长期 `ProgramVersion` 生效。

紧急风险可以先暂停受影响的未来任务；暂停不等于自动发布新计划。

## 11. 食物与营养数据

数据来源必须标记：

- `VERIFIED_DATABASE`
- `LABEL_DECLARED`
- `USER_DECLARED`
- `AI_ESTIMATED`

AI 估算至少包含：

- 参考值。
- 上下界或合理范围。
- 置信度。
- 关键假设。
- 主要不确定因素。

低置信度的单次估算不得独立触发明显的营养目标调整。

标准食物数据库、许可证、地域覆盖和数据更新机制必须先完成 Spike，不得由实现 Agent 随意选择。

## 12. 风险模型

风险采用确定性规则分级，Agent 负责识别上下文、解释和追问：

- `R0`：无明确风险，正常继续。
- `R1`：提醒，允许继续并展示注意事项。
- `R2`：限制，允许继续但必须规避或降低相关内容。
- `R3`：暂停并补充信息，暂不生成或执行受影响领域。
- `R4`：阻断并建议寻求专业帮助。

风险作用域：

- `TRAINING`
- `RECOVERY`
- `NUTRITION`
- `GLOBAL`

Agent 可以提出更高风险候选，但不得降低确定性规则已经给出的等级。

医学阈值在专业审核前统一标记为 `NEEDS_MEDICAL_REVIEW`，不得由开发者或模型自行发明。

## 13. 提醒与通知

提醒采用确定性调度：

```text
Confirmed DailySchedule
→ ReminderTask
→ 调度器按照时间、时区、免打扰和重试规则触发
→ Agent 生成个性化但不改变任务语义的文案
```

调度系统负责：

- 时区和计划时间。
- 幂等与防重复。
- 延后、跳过、过期和有限重试。
- 免打扰和用户通知偏好。
- 连续未响应后的降频。

Agent 不得绕过免打扰、擅自提高频率或通过文案修改计划和安全边界。

具体推送渠道不在本基线中冻结。

## 14. 管理员边界

`ADMIN_OPERATOR` 只允许技术性和安全性干预：

- 重试、恢复或终止失败任务。
- 暂停异常执行。
- 撤销 Session 或禁用账户。
- 查看脱敏运行上下文和审计摘要。
- 标记需要人工复核的风险事件。
- 发起待用户确认的数据修正请求。

管理员不得：

- 修改用户已确认健康事实。
- 代替用户确认计划或风险。
- 修改历史执行记录。
- 直接编辑训练、恢复或饮食内容。
- 降低确定性规则的风险等级。
- 无必要地读取完整敏感健康原文。

## 15. Phase 4 候选 Slice

以下拆分用于后续讨论，不代表已经 `READY`：

- `4A` Governance Re-baseline。
- `4B` Conversational Intake, Fact, Goal and Readiness。
- `4C` HealthProgram Core。
- `4D` Training Planning。
- `4E` Recovery Planning。
- `4F` Nutrition Planning。
- `4G` Program Generation, Review and Confirmation。
- `4H` Execution, Check-in and Feedback。
- `4I` Adjustment, Risk and Reminder。
- `4J` Web End-to-End Acceptance。

每个 Slice 必须单独建立 implementation specification、Allowed Paths、合同变更、迁移方案和 DoD。

## 16. 最终验收方向

Phase 4 最终必须同时通过：

### 16.1 完整用户旅程

```text
自然对话
→ 事实和目标确认
→ 综合计划生成
→ 分领域查看和整体确认
→ 执行
→ 反馈
→ 调整候选
→ 新版本确认
```

### 16.2 领域不变量

- 已确认版本不可原地覆盖。
- 历史执行不可静默覆盖。
- 失效候选不可确认。
- 跨领域变更保持一致。
- 新候选未确认时旧计划继续有效。

### 16.3 安全

- 用户 A 无法读取或修改用户 B 的数据。
- 管理员无法代替用户做健康业务决定。
- Agent 凭证不能跨用户、Task、Run 或 Tool Scope。
- 确定性风险规则不能被模型绕过。
- 敏感数据不进入普通日志。

### 16.4 一致性与恢复

- 重复请求不产生重复业务记录。
- Worker、API 或网络故障后任务可以安全恢复。
- 页面刷新或重新登录后状态一致。
- 提醒不重复发送且遵守免打扰。
- 调整失败时旧计划继续有效。

## 17. 明确未冻结的事项

以下问题需要后续讨论或 Spike：

- 具体训练动作库与内容审核机制。
- 恢复 Readiness 的指标、权重和阈值。
- 营养数据库、许可证、地区数据与菜品估算策略。
- 医学风险规则和升级阈值。
- 通知供应商和具体渠道。
- Web 技术栈、设计系统和离线能力。
- Phase 4 API、事件、数据库表和索引的详细合同。

任何实现 Agent 不得把本节未冻结事项自行补成架构决定。