# 0015 Context、RAG 与 Sub-Agent 边界

## 状态

已确认，2026-07-12 生效。

扩展 0011。

## 背景

长对话、历史记录和复杂任务需要上下文压缩、历史检索和任务委派，但这些能力不能形成第二套业务事实源，也不能让 Sub-Agent 获得完整用户数据和无限权限。

## 决策

- Health Platform 保存完整用户可见对话和长期业务事实。
- health-agent 只保存执行恢复、结构化 Summary 和短期上下文。
- Summary 由模型生成候选，Runtime 校验固定 Schema、引用、版本、待办项和 token budget；失败不覆盖有效版本。
- 第一版 RAG 使用 PostgreSQL + pgvector，只检索非权威历史上下文。
- 当前 Fact、当前 Plan、Profile 和 Execution 必须通过 Platform Tool 实时查询。
- 默认检索当前 Session；模型明确需要时才扩展到同一用户其他 Session。
- 主 Agent 可创建一层、顺序执行的 Sub-Agent；Sub-Agent 使用最小上下文、最小 Tool scope 和短期委派凭证。
- Sub-Agent 结果是结构化候选，由主 Agent review，不能直接发布或写正式事实。

## 影响

正面：

- 长对话可以控制 token，同时不污染业务事实。
- 历史检索具备来源、版本、失效和权限过滤。
- 复杂子任务可以隔离上下文和工具权限。

成本：

- 需要 Summary 校验、RAG 失效、rerank、检索审计和 Sub-Agent review。
- 删除和历史纠正必须同步影响索引。

## 约束

禁止索引系统 Prompt、隐藏推理、Secret、未验证猜测、完整敏感 Tool 原始输出和其他用户数据。

第一版不做并行 DAG，不允许 Sub-Agent 再创建 Sub-Agent。
