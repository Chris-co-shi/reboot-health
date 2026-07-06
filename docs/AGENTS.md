# 文档治理规则

## 唯一事实来源

- 产品定位、体验和范围：`product-scope.md`
- 系统组件、职责、调用和信任边界：`architecture.md`
- 业务聚合和不变量：`domain-model.md`
- 已实现 API、数据库和错误码：`api-db.md`
- 健康与系统安全规则：`safety-rules.md`
- 当前阶段、范围和验收状态：`mvp-exec-plan.md`
- 已确认重大决策：`decisions/`
- README 只做项目入口和真实状态摘要。

一条信息只能在一个权威文档中完整描述，其他文档使用链接或一句摘要。

## 状态表达

必须明确区分：

- `DONE`：自动化与要求的人工验收都已完成。
- `IMPLEMENTED_WITH_BLOCKERS`：代码存在，但有环境或验收阻塞。
- `IN_PROGRESS`：正在实施。
- `TODO`：尚未开始。
- `OPEN`：用户尚未确认。
- `NEEDS_TECHNICAL_SPIKE`：平台或实现可行性待验证。
- `NEEDS_MEDICAL_REVIEW`：具体医学规则缺少专业依据。

本地未提交、未构建或未运行的能力不得写成已完成。

## 文档边界

- README 不保存完整路线、字段清单或详细设计。
- product-scope 不写表结构、类名和接口路径。
- architecture 不复制数据库字段、完整 API 或页面实现细节。
- domain-model 只描述业务语义，不收纳纯技术运行模型字段表。
- api-db 只记录当前已实现或正在迁移的技术合同。
- mvp-exec-plan 只维护交付范围、状态、验收和阻塞。
- ADR 只记录已经确认且长期有效的决策；被替代时必须标记。
- 未来设想不要单独创建散落文档，先标记 OPEN，确认后进入 ADR 或里程碑。

## 变更规则

- 修改一个权威事实时，检查并删除其他文档中的重复或冲突描述。
- 删除文档时更新 README、根 AGENTS 和 decisions 索引中的引用。
- 不为让文档显得完整而虚构字段、阈值、状态或平台能力。
- 医疗阈值没有依据时统一标记 `NEEDS_MEDICAL_REVIEW`。
- 文档示例不得包含真实健康资料、真实网络地址或凭据。

## 验证

- 检查所有相对链接有效。
- 搜索已删除文档名和过时阶段名。
- 执行 `git diff --check`。
- 文档治理任务不得修改 Java、Python、Flutter 或 Vue 业务代码。