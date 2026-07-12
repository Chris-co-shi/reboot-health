# 实施规范索引

本目录保存已经批准的文件级实施规范及其完成记录；活动规范必须在 [`../PHASE_STATUS.md`](../PHASE_STATUS.md) 中标记为 `READY` 或 `IN_PROGRESS`。

## 当前状态

```text
Architecture：FROZEN
Active implementation phase：Phase 3B
Active implementation spec：NONE
```

- [`phase-3b-slice-1-repository-restructure.md`](phase-3b-slice-1-repository-restructure.md)：`DONE`

Phase 1–2C 的临时实施规范已从当前树删除。其完成证据已经汇总到 `PHASE_STATUS.md`，详细历史仍可通过 Git 记录追溯。

## 新规范准入条件

任何新文件必须至少包含：

```text
Phase / Slice
Primary Module
Goal
Authoritative Documents
Allowed Paths
Forbidden Paths
Contract Changes
Migration / Compatibility
Required Verification
Definition of Done
Out of Scope
Completion Report Template
```

要求：

1. 对应 Phase/Slice 已经由用户批准并标记 `READY`。
2. 先读取冻结文档和相关 ADR。
3. 不允许在 implementation 规范中重新定义架构、状态机、安全规则或服务职责。
4. 规范只指导一个可审查 Slice，不允许一次实现整个 Phase。
5. 完成状态、测试结果、真实验收和风险必须写回 `PHASE_STATUS.md`。

## 提示词规则

ChatGPT 生成给 Codex、Trae、Hermes、Claude Code 或 IDE Agent 的提示词必须引用当前 implementation 规范。没有活动规范时，只能执行文档分析、技术 Spike 或用户明确批准的准备工作，不能修改业务代码。
