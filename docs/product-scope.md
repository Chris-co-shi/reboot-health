# 产品范围

## 产品定位

`reboot-health` 是面向单个用户的 AI-first 健康、减脂和规律训练辅助系统。

产品核心不是让用户维护复杂后台，而是让 Agent 通过自然语言理解目标、限制和执行反馈，在确定性工具、安全边界、确认和审计约束下提供可解释的行动建议与计划提案。

本项目不做医学诊断，不替代医生意见。

## 当前工程定位

当前与目标运行形态是 Python-first 模块化单体：

```text
用户入口
→ Agent Runtime
→ OpenAI-compatible LLM
→ 受控 Tool Runtime
→ Domain Service
→ Persistence（后续阶段）
```

项目工程价值不只是调用模型，而是建设：

- 通用有限轮次 Agent Loop。
- 可声明、可校验、可审计的 Tool Contract。
- 最小必要 Context。
- 确定性 Safety Guard。
- Confirmation Pause/Resume。
- 候选与已确认事实分离。
- Trace、Evaluation 和 Recovery。

历史 Java、Flutter、Vue 和 Compose 代码仍在仓库中，但属于 legacy，不是当前产品入口。正式客户端形态将在 API 和领域闭环稳定后单独确认。

## 核心原则

- 用户主要通过自然语言表达现状、目标、偏好和不适。
- Agent 可以直接回答，也可以按需调用受控工具；不要求每个请求都进入固定流程。
- 模型输出默认是解释、候选或草案，不自动变成已确认事实。
- 确定性安全规则优先于模型输出。
- 重要健康事实、目标变化、计划发布和训练负荷增加必须进入确认边界。
- Tool 只能执行声明过的能力，不开放 shell、任意文件系统或任意 SQL。
- 产品默认采用单 Agent；只有未来出现明确上下文隔离或专门权限需求时才评估 Subagent。
- 项目保持模块化单体，不引入微服务、消息队列或重量级工作流平台。

## 第一条产品闭环

长期目标闭环：

```text
自然语言描述
→ Agent 按需读取已确认档案与近期执行数据
→ 必要时提出关键澄清问题
→ 生成计划或调整提案
→ 确定性 Safety Guard
→ 用户确认
→ 发布新的计划版本
→ 今日执行反馈
→ 周期复盘与下一次调整
```

当前实施顺序不是固定业务工作流，而是先建立通用 Runtime 基础：

```text
Phase 1：真实 Provider 与兼容链路
Phase 2A：通用只读 Tool Call Agent Loop
Phase 2B：只读健康上下文工具
Phase 2C：Session / Events / Persistence
Phase 3：Safety Guard
Phase 4：Proposal / Confirmation / Publish
```

当前状态以 [`mvp-exec-plan.md`](mvp-exec-plan.md) 为准。

## 交互方式

当前开发入口是 CLI/Console，用于验证 Runtime、Tool Call 和模型行为。

未来正式体验仍倾向“自然语言 + 结构化卡片”：

- 自然语言用于描述目标、补充状态、回答追问和理解原因。
- 结构化卡片用于候选、计划提案、确认、执行反馈和趋势。

正式客户端选型尚未确认，不再把 Flutter 作为默认当前目标。客户端应只通过正式产品 API 使用能力，不直接访问数据库或内部 Tool handler。

## 自动化与确认

无需确认：

- 普通知识解释。
- 只读查询。
- 纯计算 Tool。
- 生成未发布的草案或提案。

通常需要确认：

- 将模型推断写为用户健康事实。
- 增加训练负荷或风险。
- 修改重要目标或健康限制。
- 发布新计划版本。
- 执行不可逆或高影响写操作。

Confirmation 是 Runtime 暂停恢复协议，不设计成普通模型 Tool。

## 数据输入原则

- 优先读取已确认事实、执行记录和设备/系统已有数据。
- 模型不能把推断自动写成事实。
- 信息不足时一次只询问对当前任务最关键的问题。
- Runtime 不硬编码用户健康信息。
- 普通日志不保存完整健康原文、完整 prompt 或 raw model response。

## 当前不做

- 医学诊断、处方或替代医生建议。
- 未经确认发布计划或增加训练风险。
- 公开多用户平台、运营后台、社区、排行榜、商城和支付。
- 默认多 Agent、复杂 Subagent 编排。
- 微服务、消息队列、Kubernetes 或工作流引擎。
- 在线训练基础模型。
- Shell、任意文件系统和任意 SQL Tool。
- 在 Phase 2A 中实现数据库、Memory、Safety Guard、Confirmation 或写操作 Tool。

## 待确认

- `OPEN`：正式客户端采用 Flutter、Web 或其它形态。
- `OPEN`：本地持久化最终采用 SQLite 还是其它方案。
- `OPEN`：模型调用数据保留周期。
- `OPEN`：提醒静默时段和主动询问次数上限。
- `NEEDS_TECHNICAL_SPIKE`：健康设备数据接入方式。
- `NEEDS_MEDICAL_REVIEW`：具体安全阈值和规则依据。
