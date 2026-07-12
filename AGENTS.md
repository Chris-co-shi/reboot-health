# 仓库级 Agent 规则

## 1. 语言和真实性

- 所有计划、说明、提示词、完成报告和自查使用中文。
- 代码标识符遵循目标模块现有规范。
- 不得把未实现、未运行、仅 Mock 或仅静态检查的能力描述为完成。
- 遇到不确定事实先读取仓库，不允许凭经验或历史对话猜测当前实现。

## 2. 架构状态

```text
Architecture Status：FROZEN
Frozen At：2026-07-12
Active Implementation Phase：Phase 3B（当前无活动 Slice）
```

自冻结日起，项目唯一事实来源是 [`docs/README.md`](docs/README.md) 中列出的权威文档。

任何代码、测试、部署、Issue、PR、提示词、聊天结论或旧 ADR 与冻结文档冲突时，以冻结文档为准，并先报告冲突。

## 3. 强制阅读顺序

开始任何任务前按顺序读取：

```text
AGENTS.md
→ docs/README.md
→ docs/PHASE_STATUS.md
→ 与任务有关的权威文档
→ 相关 ADR
→ 当前 implementation 规范
→ 目标模块 AGENTS.md / README.md
```

没有 `READY` 或 `IN_PROGRESS` Slice、没有 implementation 规范时，禁止修改业务代码。

## 4. 冻结架构摘要

目标系统：

```text
Mini Program / Flutter / Vue Admin
                ↓
          Health Platform
                ↓ mTLS + short-lived JWT
            health-agent
```

- Health Platform：用户身份、业务权限、Conversation、Fact、Plan、Risk、File、Secret、审计和正式 API 权威。
- health-agent：Task/Run/Step、模型、Tool、Checkpoint、Context、RAG、Sub-Agent、Sandbox 和执行可观测性。
- PostgreSQL：业务和执行权威。
- Redis Streams：调度/协调，不是事实源。
- MinIO：第一版对象存储。
- Kubernetes：6 VM，3 Control Plane + 3 Worker，全部组件运行在 K8s 内。

完整规则必须读取冻结文档，不得依赖本摘要实现。

## 5. 当前实现事实

`health_agent/` 中 Phase 1–2C 已完成或显式完成：

- OpenAI-compatible Provider。
- 通用有限轮次 Tool Call Loop。
- ToolRegistry、ToolExecutor、`convert_weight_unit`。
- Session Message History 和 interactive CLI。
- JSON Store、CAS、lease、heartbeat、fencing。
- checkpoint、stale recovery、orphan maintenance。

当前 CLI/JSON Store 是迁移基础，不是生产目标架构。

- `health_platform/` 是 Phase 3B 建立的框架无关 Python 业务平台骨架，尚未实现业务能力。
- `clients/flutter/` 是正式用户客户端空壳，`clients/miniapp/` 是正式用户客户端边界占位。
- `frontend/` 是正式 Vue 3 Admin 空壳，`deploy/` 是 Kubernetes 目标目录占位。
- `contracts/` 是未来可机读跨服务合同的共享目录，当前权威语义仍来自 `docs/API_CONTRACTS.md`。

## 6. 任务准入

每个代码任务必须先声明：

```text
Phase / Slice:
Primary Module:
Goal:
Authoritative Documents:
Allowed Paths:
Forbidden Paths:
Contract Changes:
Migration / Compatibility:
Required Verification:
Definition of Done:
Out of Scope:
```

缺少任一关键项时只能做分析，不能开始实现。

## 7. 路径和范围

- 每个 Slice 只有一个 Primary Module。
- 只修改 Allowed Paths。
- 不得为了“顺手完善”修改后续 Phase。
- 不得新增第二套 Contract、状态机、事实源或发布引擎。
- 跨服务修改必须先更新 API/事件合同和兼容策略。
- 删除 legacy 前必须证明关键语义已迁移、测试已覆盖、引用已清理并有回滚方案。
- 不覆盖、不删除、不 stash 用户未提交修改。

## 8. 文档先行

架构或产品变化必须：

```text
提出变化
→ ADR
→ 更新全部受影响权威文档
→ 用户批准
→ PHASE_STATUS / implementation 规范
→ 代码
```

禁止：

- 代码先行后补文档。
- 通过 Prompt 重新定义架构。
- 在实现中自行决定 OPEN/Spike/医学审核事项。
- 用测试实现反向降低冻结合同。

## 9. 提示词治理

ChatGPT 生成给 Codex、Trae、Hermes、Claude Code 或其他 Agent 的实施提示词必须：

1. 指定 Phase/Slice。
2. 要求先阅读完整权威文档和相关 ADR。
3. 明确 Allowed/Forbidden Paths。
4. 明确合同、迁移和验收。
5. 明确不得扩大范围、放宽安全或提前实现后续 Phase。
6. 要求完成报告写回 `docs/PHASE_STATUS.md`。

没有活动 implementation 规范时，不生成“直接实现整个 Phase”的提示词。

## 10. 服务边界

### Health Platform

负责业务权威。不得把以下职责移入 health-agent：

- 用户业务 RBAC。
- HealthFact/Goal/Plan/Execution/Risk 正式状态。
- 文件归属和删除决定。
- Secret 长期存储。
- 用户确认和业务审计。

### health-agent

负责通用执行。不得：

- 直接连接 Platform 数据库。
- 把 Summary/RAG/模型结果写成正式 Fact。
- 直接发布 Plan。
- 代表用户确认风险。
- 保存长期用户业务画像。

## 11. Runtime 和 Tool 规则

- ModelProvider 只调用模型、转换消息/Tool Schema、解析响应和归一化 Provider 错误。
- Runtime 管理 Task/Run/Step、消息、预算、Tool 调度、Checkpoint、lease/fencing 和恢复。
- ToolRegistry 只允许白名单 Tool。
- Tool 必须声明 executionMode、风险、网络、文件、Secret、副作用、幂等和补偿。
- 未明确批准不得开放通用 Shell、任意文件系统、任意 SQL 或无限制网络。
- 文件解析、代码执行和不可信内容必须进入 Sandbox。
- 结果不确定的副作用不得自动重放。

## 12. Fact、Plan 和风险

- 模型、Summary、RAG、OCR 和 Tool 输出默认是候选。
- 文件提取健康字段必须逐项确认。
- Plan 候选整体确认后发布；旧 Plan 在新候选确认前继续有效。
- 已完成执行记录不可被 Plan 修订改变。
- 历史 Fact 纠正需要二次确认和修订历史。
- 健康风险需要证据、替代方案和必要的二次确认。
- 越权、跨用户、Secret、数据损坏、非法状态和未知副作用必须 fail-closed。

## 13. 隐私和日志

禁止提交或记录：

- 真实用户健康资料。
- API Key、Token、Secret、签名 URL。
- 完整 Prompt、隐藏推理和 raw model response。
- 完整敏感 Tool 返回。
- 本机绝对路径、真实内部地址和凭据。

Trace 只记录 ID、状态、次数、延迟、错误分类、模型/Tool 名称和脱敏摘要。

## 14. 测试规则

- 不为了测试通过删除测试、放宽断言、绕过权限或降低状态机要求。
- 普通单元测试不访问真实模型、真实 Secret、生产数据库或公网。
- 跨服务合同必须有 consumer/provider 或等价兼容测试。
- 状态机、幂等、Outbox/Inbox、版本冲突、跨用户、删除和恢复必须自动化验证。
- 真实 LLM、K8s、数据库故障转移和备份恢复必须显式执行并记录环境与结果。

当前 Runtime 回归命令：

```bash
cd health_agent
python3 -m compileall agent tests scripts
python3 -m unittest discover -s tests -v
```

## 15. 完成报告

每次实现完成必须报告：

- Phase/Slice 和 Primary Module。
- 修改、新增、删除文件。
- 合同和迁移变化。
- 实际验证命令和结果。
- 真实环境验收结果。
- 未验证项、限制和风险。
- 是否越过 Allowed Paths。
- `docs/PHASE_STATUS.md` 更新。

未写回 Phase 状态的实现不算完整交付。
