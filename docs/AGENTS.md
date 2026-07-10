# 文档治理规则

## 唯一事实来源

- 产品定位、体验和范围：`product-scope.md`
- 系统组件、职责、调用和信任边界：`architecture.md`
- 业务聚合和不变量：`domain-model.md`
- 历史已实现 API、数据库和迁移参考：`api-db.md`
- 健康与系统安全规则：`safety-rules.md`
- 当前阶段、范围、状态和验收结果：`mvp-exec-plan.md`
- 已确认重大决策：`decisions/`
- 已确认阶段的文件级实施交接：`implementation/`
- README 只做项目或模块入口、核心价值和真实状态摘要。

一条信息只能在一个权威文档中完整描述，其他文档使用链接或一句摘要。

## Implementation 规范

`implementation/` 只允许保存已经在 `mvp-exec-plan.md` 中标记为 `READY` 或 `IN_PROGRESS` 的阶段规范。

实施规范可以包含：

- Primary Module、Allowed Paths、Forbidden Paths。
- 文件级修改建议和实施顺序。
- Contract 草案、伪代码和错误策略。
- 测试矩阵、真实环境验收和 Definition of Done。
- IDE Agent/人工开发的完成报告模板。

实施规范不得：

- 自己声明阶段已经完成。
- 重复完整架构背景或产品范围。
- 提前实现后续阶段设计。
- 把未确认方案写成长期架构决策。

阶段完成状态只能更新在 `mvp-exec-plan.md`；长期有效决策进入 ADR。

## README 视觉与结构规范

所有 `README.md` 必须保持现代、简洁、可扫描：

- 顶部优先使用居中标题、短副标题和少量静态技术徽章。
- 徽章只能表达稳定事实；没有真实 CI 时禁止伪造 build、coverage 或 release 状态。
- 首屏必须回答：这是什么、解决什么问题、当前是否可用。
- 优先使用短段落、表格、Mermaid、代码块和清晰状态提示。
- 每个一级运行时目录应有模块 README，包含定位、职责边界、当前状态、运行或验证命令、相关文档。
- 使用当前术语：Python-first 模块化单体、Agent Runtime、ModelProvider、Tool Runtime、legacy compatibility adapter。
- 历史 Java Health Domain Kernel、Flutter Client 和 Vue Debug Tool 只在 legacy/迁移上下文中使用。
- 命令必须可复制；未验证命令和平台必须明确标注。
- 不重复完整架构、字段清单或实施规范，使用链接指向权威文档。
- 不使用会快速失效的截图、营销数字或未经验证的能力描述。

## 状态表达

必须明确区分：

- `DONE`：自动化验证和要求的真实运行验收都完成。
- `READY`：范围、设计和验收标准已确认，可以开始实现。
- `IN_PROGRESS`：正在实施。
- `IMPLEMENTED_WITH_BLOCKERS`：主体存在，但仍有关键验收阻塞。
- `TODO`：尚未开始。
- `BLOCKED`：被依赖或未确认事项阻塞。
- `OPEN`：用户尚未确认。
- `NEEDS_TECHNICAL_SPIKE`：技术可行性待验证。
- `NEEDS_MEDICAL_REVIEW`：具体医学规则缺少专业依据。

本地未提交、未构建、未运行真实链路或只通过 Mock 的能力不得写成 `DONE`。

## 文档边界

- README 不保存完整路线、字段清单或详细设计。
- product-scope 不写表结构、类名和接口路径。
- architecture 不复制完整测试用例或逐文件操作步骤。
- implementation 不重复阶段状态和长期架构背景。
- domain-model 只描述业务语义，不收纳纯技术运行模型字段表。
- api-db 记录历史已实现合同和后续迁移参考，不得暗示旧链路当前可运行。
- mvp-exec-plan 只维护阶段范围、状态、验收和阻塞。
- ADR 只记录已经确认且长期有效的决策；被替代时必须标记。
- 未确认设想先标记 OPEN，确认后进入 ADR、里程碑或 implementation 规范。

## 变更规则

- 修改一个权威事实时，检查并删除其他文档中的重复或冲突描述。
- 新增 implementation 规范时，必须同步 `implementation/README.md`、`docs/README.md` 和 `mvp-exec-plan.md`。
- 新增或替代 ADR 时，必须同步 `decisions/README.md`，被替代 ADR 正文必须链接新 ADR。
- 删除文档时更新所有索引和相对链接。
- 不为让文档显得完整而虚构字段、阈值、状态或平台能力。
- 医疗阈值没有依据时统一标记 `NEEDS_MEDICAL_REVIEW`。
- 文档示例不得包含真实健康资料、真实网络地址或凭据。

## 验证

- 检查所有相对链接有效。
- 搜索已删除文档名和过时阶段名。
- 检查当前状态是否与代码和真实验收一致。
- 执行 `git diff --check`。
- 文档治理任务不得修改 Java、Python、Flutter、Vue 或部署业务代码。
