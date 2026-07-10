# 0010 Python 模块化单体与通用 Agent Loop

## 状态

已确认。

本 ADR 替代 [`0009 Python Health Agent Harness 与可信领域内核`](0009-ai-first-product-and-module-boundaries.md) 中“Python 编排、Java 事实与安全权威、Flutter 正式客户端”的多运行时职责划分。

本 ADR 扩展 [`0002 模块化单体架构`](0002-modular-monolith.md)：模块化单体原则继续有效，但当前目标实现统一迁移到 Python。

## 背景

历史方案将智能控制流放在 Python，将事实、安全、确认、持久化和审计放在 Java，并通过 Flutter/Java/Python 多运行时链路交互。

实际重构过程中已经确认：

- 当前真实运行目录是 `health_agent/`。
- 产品 Provider 已直接接入 OpenAI-compatible LLM。
- Java/Python HTTP 链路与旧 Compose 启动链路不可用。
- 继续维护多运行时合同会增加迁移成本并掩盖真实可运行路径。
- 项目目标是单人私有健康 Agent，不需要微服务、消息队列或复杂工作流平台。

因此项目统一迁移为 Python-first 模块化单体，并按纵向切片逐步迁移确定性业务能力。

## 决策

### 1. 运行时形态

`health_agent/` 是当前与目标 Python Runtime。

```text
用户入口
→ Agent Runtime
→ ModelProvider
→ Tool Registry / Executor
→ Domain Service
→ Repository Port
→ Persistence Adapter
```

历史 `backend/`、`clients/flutter/`、`frontend/` 和 `deploy/` 保留为 legacy，除非单独批准迁移任务，否则不继续扩展。

### 2. 智能与确定性边界

- LLM 理解用户意图并决定直接回答或请求工具。
- Agent Runtime 管理消息、模型回合、工具调度、运行限制、错误收敛和后续暂停恢复协议。
- Tool 与 Domain Service 执行确定性代码、校验和业务状态转换。
- Repository Port 与 Persistence Adapter 负责持久化。
- Safety、Confirmation、幂等和审计必须由确定性代码实现，不能仅依赖 Prompt 或模型自觉。

### 3. 通用 Agent Loop

通用产品入口采用有限轮次循环：

```text
User Message
→ Model Turn
→ Assistant content 或 Tool Call
→ Tool 校验与执行
→ role=tool Result
→ 下一次 Model Turn
→ Final content
```

约束：

- 不使用固定 Planner/Executor/Reviewer/Publisher 流程。
- 不要求每个请求调用工具。
- 不解析普通文本中的伪函数调用。
- 不允许无限循环或隐式无限重试。
- Subagent 只在未来确有上下文隔离或专门权限需求时单独决策，不作为默认架构。

### 4. Phase 2A 边界

Phase 2A 只实现通用**只读** Tool Call Loop：

- 支持 system/user/assistant/tool 消息。
- 支持一个 assistant 回合中的多个 Tool Call，按顺序执行。
- 支持结构化 Tool Error 返回模型。
- 支持最大模型回合、最大工具次数和整体超时。
- 提供正式只读工具 `convert_weight_unit` 验证真实链路。

Phase 2A 不实现：

- 写操作 Tool。
- Safety Guard。
- Confirmation Pause/Resume。
- 数据库和 Memory。
- Plan Publish。
- 多 Agent、Subagent、DAG 或工作流引擎。

详细实施规范见 [`../implementation/phase-2a-read-only-tool-call-loop.md`](../implementation/phase-2a-read-only-tool-call-loop.md)。

### 5. 兼容路径

`INITIAL_PLANNING` 只作为临时兼容适配器保留，不再作为通用产品入口，也不得反向决定通用 Runtime 结构。

### 6. 测试替身

- 产品 Bootstrap 只使用真实 OpenAI-compatible Provider。
- Scripted Provider 只能位于 `health_agent/tests/`。
- 普通单元测试不得访问真实网络或本地密钥。
- 真实 LLM 验收必须显式执行并如实记录。

## 影响

### 正面影响

- 只有一个当前真实运行时和一个 Composition Root。
- Provider、Runtime、Tool、Domain、Persistence 职责更清晰。
- 降低跨运行时 HTTP、重复 Schema 和部署链路成本。
- IDE Agent 可以依靠同一套文档和测试边界继续开发。

### 迁移成本

- 旧 Java 领域不变量、PlanVersion、revision、幂等、审计和确认语义必须在后续阶段迁移后才能删除 legacy 实现。
- 历史架构、MVP 路线和 ADR 需要标记为已替代或历史事实。
- 当前 Python Runtime 在 Persistence、Safety 和 Confirmation 完成前仍不是完整产品闭环。

## 非目标

- 不在本 ADR 中决定数据库具体 Schema。
- 不在本 ADR 中实现医疗规则或阈值。
- 不引入微服务、消息队列、向量数据库或重量级工作流平台。
- 不建设默认多 Agent 编排。
