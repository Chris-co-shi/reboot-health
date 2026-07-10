# 实施规范索引

本目录只保存**已经确认进入实施阶段**的工程交接规范，用于在 Codex、IDE Agent 或人工开发之间切换时保持同一目标、边界和验收口径。

实施规范不是完成状态来源：

- 架构职责与稳定边界见 [`../architecture.md`](../architecture.md)。
- 当前阶段、状态和验收结果见 [`../mvp-exec-plan.md`](../mvp-exec-plan.md)。
- 长期有效的架构决策见 [`../decisions/`](../decisions/README.md)。

## 当前规范

| 阶段 | 状态 | 文档 | 目标 |
|---|---|---|---|
| Phase 2A | `READY` | [`phase-2a-read-only-tool-call-loop.md`](phase-2a-read-only-tool-call-loop.md) | 建立真实 LLM → 只读 Tool Call → Tool Result → 真实 LLM 的有限轮次 Agent Loop |

## 使用规则

1. 开发前先读取根目录 `AGENTS.md`、`health_agent/AGENTS.md` 和对应实施规范。
2. 实施规范中的禁止范围不得被 IDE Agent 自行扩大。
3. 规范中标记为后续阶段的能力不得提前实现。
4. 实际完成状态只能在 `mvp-exec-plan.md` 中更新。
5. 代码实现与规范冲突时必须停止并报告，不得通过放宽测试或删除校验解决。
