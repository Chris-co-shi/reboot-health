# 实施规范索引

本目录只保存**已经确认进入实施阶段**的工程交接规范，用于在 Codex、IDE Agent 或人工开发之间切换时保持同一目标、边界和验收口径。

实施规范不是完成状态来源：

- 架构职责与稳定边界见 [`../architecture.md`](../architecture.md)。
- 当前阶段、状态和验收结果见 [`../mvp-exec-plan.md`](../mvp-exec-plan.md)。
- 长期有效的架构决策见 [`../decisions/`](../decisions/README.md)。

## 当前规范

| 阶段 | 状态 | 文档 | 目标 |
|---|---|---|---|
| Phase 2C | `READY` | [`phase-2c-interactive-session-cli.md`](phase-2c-interactive-session-cli.md) | 建立连续对话、显式 JSON Session 恢复和最小交互式 CLI |

## 已完成阶段参考

| 阶段 | 状态 | 文档 | 用途 |
|---|---|---|---|
| Phase 2A | `DONE` | [`phase-2a-read-only-tool-call-loop.md`](phase-2a-read-only-tool-call-loop.md) | 保留真实 LLM → Tool Call → Tool Result → LLM 的实施与验收依据 |

## 使用规则

1. 开发前先读取根目录 `AGENTS.md`、`health_agent/AGENTS.md` 和当前阶段实施规范。
2. 实施规范中的禁止范围不得被 IDE Agent 自行扩大。
3. 规范中标记为后续阶段的能力不得提前实现。
4. 实际完成状态只能在 `mvp-exec-plan.md` 中更新。
5. 已完成阶段规范不得被误读为当前待实施任务。
6. 代码实现与规范冲突时必须停止并报告，不得通过放宽测试或删除校验解决。
