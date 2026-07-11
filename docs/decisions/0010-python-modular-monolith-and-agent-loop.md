# 0010 Python 模块化单体与通用 Agent Loop

## 状态

**部分保留 / 目标架构已替代。**

- Python 通用 Agent Loop、ModelProvider、ToolRegistry/Executor、有限轮次、测试替身隔离和 `INITIAL_PLANNING` legacy compatibility 语义继续有效。
- “整个产品迁移为 Python 模块化单体、不引入微服务/Redis/Kubernetes/Sub-Agent”的目标已经被 2026-07-12 架构冻结替代。

替代 ADR：

- [`0012 Health Platform 与 health-agent 服务拆分`](0012-health-platform-and-agent-service-split.md)
- [`0013 持久异步执行、调度与事件同步`](0013-durable-agent-execution-and-event-sync.md)
- [`0015 Context、RAG 与 Sub-Agent 边界`](0015-context-rag-and-subagent-boundaries.md)
- [`0017 六 VM Kubernetes 与架构冻结`](0017-kubernetes-six-vm-and-architecture-freeze.md)

## 保留的历史实现结论

Phase 1–2C 已验证并必须迁移复用：

- OpenAI-compatible Provider。
- system/user/assistant/tool 消息合同。
- 有限轮次 Tool Call Agent Loop。
- Tool 白名单、参数校验和结构化错误。
- Session Message History。
- lease、fencing、checkpoint 和保守恢复。
- interactive Session CLI。

## 不再有效的结论

以下内容不能再用于未来实现或提示词：

- 产品最终是单个模块化单体部署。
- 不引入服务间 HTTP。
- 不引入 PostgreSQL 生产 Task Store、Redis Streams 或 Kubernetes。
- 不建设 Sub-Agent、RAG、Sandbox、MinIO 或管理端。

当前规则以 [`../README.md`](../README.md) 列出的冻结文档为准。旧完整内容可通过 Git 历史追溯。
