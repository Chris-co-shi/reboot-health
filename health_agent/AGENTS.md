# health-agent Runtime 规则

## 1. 当前定位

`health_agent/` 是已完成 Phase 1–2C 的 Python Agent Runtime，也是未来独立 `health-agent` 服务的迁移基础。

它当前不是完整 Health Platform，不是生产 API/Worker 部署，也不是业务事实权威。

开始任何任务先读取：

```text
../AGENTS.md
→ ../docs/README.md
→ ../docs/PHASE_STATUS.md
→ ../docs/SYSTEM_ARCHITECTURE.md
→ ../docs/STATE_MACHINES.md
→ ../docs/API_CONTRACTS.md
→ ../docs/SECURITY_AND_PRIVACY.md
→ 当前 implementation 规范
```

当前没有活动 implementation 规范，因此禁止直接开始 Phase 3B+ 业务代码。

## 2. 已实现事实

- OpenAI-compatible Provider。
- system/user/assistant/tool 消息合同。
- GenericAgentLoop。
- ToolRegistry / ToolExecutor。
- `convert_weight_unit`。
- Session Message History。
- Confirmation 基础合同。
- JSON Store、CAS、lease、heartbeat、fencing。
- execution checkpoint、stale recovery、orphan maintenance。
- `scripts/agent_chat.py` interactive CLI。

这些能力迁移时必须保留语义和回归测试。

## 3. 目标职责

未来独立 health-agent 负责：

- Agent Task、Run、Step 和 Checkpoint。
- 模型、Tool、预算、Provider fallback。
- API/Worker 执行分离。
- Redis Streams 调度和 PostgreSQL reconciler。
- Context、Summary、RAG、Sub-Agent。
- Sandbox、Tool 策略和执行 Trace。
- Outbox、回调、事件重放和管理查询。

## 4. 永久禁止承担的职责

health-agent 不得：

- 实现最终用户登录和业务 RBAC。
- 直接连接 Health Platform 数据库或修改其表。
- 保存正式 HealthFact、Goal、Plan、ExecutionRecord 或 RiskAcknowledgement。
- 把模型、Summary、RAG、OCR 或 Tool 输出直接写成正式事实。
- 直接发布 Plan。
- 代表用户确认风险或历史纠正。
- 保存长期业务 Secret。

业务数据只能通过 Health Platform 内部 Tool API 访问。

## 5. Provider

Provider 只负责：

- 调用模型。
- 转换消息和 Tool Schema。
- 解析 content、tool_calls、usage、finish reason 和必要 metadata。
- 归一化 Provider 错误。

Provider 不读取 `.env`、不执行 Tool、不访问数据库、不选择业务状态、不自动扩大权限。

## 6. Runtime

Runtime 负责：

- 有限轮次 Model/Tool Loop。
- Session/Task/Run/Step 技术状态。
- budget、timeout、retry policy。
- lease、heartbeat、fencing。
- checkpoint 和恢复分类。
- Context/Summary/RAG/Sub-Agent 调度。
- 事件和 Trace 摘要。

`MODEL_CALL_IN_FLIGHT`、`TOOL_CALL_IN_FLIGHT` 和 `FINALIZING` 默认不能自动重放。

## 7. Tool

Tool 必须白名单注册并声明：

```text
executionMode
riskLevel
networkPolicy
filesystemPolicy
secretRefs
timeout
resourceLimits
sideEffect
idempotency
compensationPolicy
```

- Platform Read Tool 可以在 Worker 内执行。
- 文件解析、Shell/代码和不可信第三方内容必须进入 Sandbox。
- 未经批准不开放通用 Shell、任意文件系统、任意 SQL 或无限制网络。
- 结果不确定的副作用进入人工处理。
- 补偿必须来自显式 ToolDefinition，模型不能临时编造。

## 8. Context 与业务事实

```text
Message History / Summary / RAG = 执行上下文
HealthFact / Plan / Execution / Risk = Health Platform 业务权威
```

Summary 和 RAG 不得覆盖业务事实。当前 Fact 和 Plan 必须通过 Platform Tool 实时查询。

## 9. Sub-Agent

第一版：

- 顺序执行。
- 委派深度 1。
- 最小上下文和 Tool scope。
- 短期 Task/Run/SubTask token。
- 结构化结果由主 Agent review。

不得直接发布 Plan、写正式 Fact 或继续创建 Sub-Agent。

## 10. 隐私和 Secret

禁止把以下内容写入日志、Trace、Checkpoint、Redis、模型或 Tool Result：

- API Key、Token、Secret、签名 URL。
- 完整 Prompt、隐藏推理和 raw model response。
- 完整敏感健康原文和文件内容。

Secret 由 Health Platform 临时签发，优先通过 tmpfs 或文件描述符注入。

## 11. 当前回归验证

```bash
cd health_agent
python3 -m compileall agent tests scripts
python3 -m unittest discover -s tests -v
```

涉及 lease、checkpoint、recovery 和 JSON Store 时运行专项测试。未来 PostgreSQL/API/Worker 实现必须增加分布式、幂等和故障恢复验收，不能删除现有测试来迁移。

## 12. 代码任务准入

没有 `READY` Slice 时，只允许：

- 阅读和分析。
- 用户批准的技术 Spike。
- 修复明确的 Phase 1–2C 回归缺陷。
- 文档一致性修复。

任何新架构能力必须先有 implementation 规范。
