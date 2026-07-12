# Health Platform 规则

开始任务前必须依次读取：

```text
../AGENTS.md
→ ../docs/README.md
→ ../docs/PHASE_STATUS.md
→ 相关冻结权威文档
→ ADR 0012–0017
→ 当前 implementation 规范
```

Health Platform 是用户身份、业务权限、Conversation、Fact、Goal、Plan、Execution、Risk、File、Secret、确认和业务审计的唯一权威。

- 客户端只访问 Health Platform。
- Health Platform 通过 mTLS + 短期 JWT 调用 `health-agent`。
- `health-agent` 不得直连 Platform 数据库。
- 模型、Summary、RAG、OCR 和 Tool 输出默认是候选。
- 不得自行创造第二套状态机、API、合同、事实源或 Plan 发布引擎。
- 没有 `READY`/`IN_PROGRESS` Slice 和 implementation 规范时，不得实现业务、选择 Web 框架、创建数据库 Schema 或正式 Endpoint。

当前目录仅为 Phase 3B 骨架，不得描述为已实现业务服务。
