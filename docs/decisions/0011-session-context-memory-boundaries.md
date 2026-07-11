# 0011 Session、Context、Memory 与领域事实边界

## 状态

**已扩展。** 基础分层继续有效，完整规则由以下文档和 ADR 扩展：

- [`../DOMAIN_MODEL.md`](../DOMAIN_MODEL.md)
- [`../SYSTEM_ARCHITECTURE.md`](../SYSTEM_ARCHITECTURE.md)
- [`0015 Context、RAG 与 Sub-Agent 边界`](0015-context-rag-and-subagent-boundaries.md)

## 继续有效的核心结论

```text
Session Message History ≠ 长期 Memory
Runtime Context ≠ 持久化业务模型
Conversation Summary ≠ 已确认健康事实
RAG 结果 ≠ 当前业务权威
Memory Candidate ≠ 自动生效的领域事实
```

- 用户可见 Conversation 和 Message 的权威在 Health Platform。
- health-agent 的 Session、Summary 和 Checkpoint 是执行技术状态。
- UserProfile、HealthFact、Goal、Plan、ExecutionRecord 和 Risk 由 Health Platform 管理。
- 普通 Clarification 使用同一 Session 的下一条用户消息，不创建 PendingAction。
- 模型不能把对话摘要或一次推断自动写成长期 Fact。
- Session 删除不自动删除已经确认的业务事实。

## 2026-07-12 扩展结论

- Summary 使用固定 Schema、版本和 Runtime 校验。
- 第一版 RAG 使用 PostgreSQL + pgvector，只处理非权威历史上下文。
- 当前 Fact、当前 Plan 和执行数据必须通过 Platform Tool 实时读取。
- RAG 默认限定当前 Session，需要时才扩展到同一用户其他 Session。
- 纠正、失效和删除必须立即排除旧 Chunk，再异步重建。
- 主 Agent 可以使用一层顺序 Sub-Agent；Sub-Agent 只能获得最小上下文和 Tool scope。

## 隐私

禁止将完整 Prompt、隐藏推理、Secret、未验证模型猜测、完整敏感 Tool 原始结果或其他用户内容写入 Summary/RAG/普通日志。

旧完整内容可通过 Git 历史追溯；当前实现必须读取冻结文档，不得只依赖本 ADR。
