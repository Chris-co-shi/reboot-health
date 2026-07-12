<div align="center">

# reboot-health Architecture Documentation

### Frozen architecture with governed Phase 4 product discovery

![Architecture](https://img.shields.io/badge/Architecture-FROZEN-6C5CE7)
![Phase%204](https://img.shields.io/badge/Phase%204-DISCOVERY-0984E3)
![Language](https://img.shields.io/badge/Language-Chinese-E17055)

</div>

> **架构状态：`FROZEN`。** 自 2026-07-12 起，本目录是 reboot-health 产品与工程的唯一事实来源。已批准 ADR 可以调整阶段边界，但代码、测试、部署清单、Issue、PR、Codex/IDE Agent 提示词和人工实现不得与本目录冲突。

## 1. 权威文档

| 文档 | 唯一职责 |
|---|---|
| [`PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md) | 产品目标、角色、客户端体验、Plan/风险/文件与人工决策原则 |
| [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) | Health Platform、health-agent、客户端、数据流与服务边界 |
| [`DOMAIN_MODEL.md`](DOMAIN_MODEL.md) | Session、Task、Run、Fact、Plan、Risk、File 等领域语义与不变量 |
| [`STATE_MACHINES.md`](STATE_MACHINES.md) | Task、Run、Plan、Fact、File、风险确认和删除状态机 |
| [`API_CONTRACTS.md`](API_CONTRACTS.md) | 客户端 API、Agent API、Tool API、事件、SSE、幂等和错误合同 |
| [`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md) | 身份、mTLS/JWT、Sandbox、Secret、数据保留、删除和审计 |
| [`DEPLOYMENT_AND_OPERATIONS.md`](DEPLOYMENT_AND_OPERATIONS.md) | Kubernetes、六 VM、存储、灰度、迁移、备份、监控和恢复 |
| [`PHASE_STATUS.md`](PHASE_STATUS.md) | 阶段状态、已完成证据、后续实施顺序、阻塞和已知风险 |
| [`PHASE_4_BASELINE.md`](PHASE_4_BASELINE.md) | 已确认的 Phase 4 产品范围、综合健康计划、交互原则、风险和最终验收方向；当前为 Discovery 基线，不是实施规范 |
| [`decisions/`](decisions/README.md) | 已批准或被替代的 Architecture Decision Records |
| [`implementation/`](implementation/README.md) | 仅保存已经批准实施的文件级交接规范；Discovery 文档不能替代 implementation specification |
| [`design/health-platform/`](design/health-platform/README.md) | Health Platform 模块化单体、Identity、数据、安全与运行详细设计 |

## 2. 优先级

发生冲突时按以下顺序裁决：

```text
已批准 ADR
→ PRODUCT_REQUIREMENTS / SECURITY_AND_PRIVACY
→ SYSTEM_ARCHITECTURE / DOMAIN_MODEL
→ PHASE_4_BASELINE（仅 Phase 4 产品 Discovery 范围）
→ STATE_MACHINES / API_CONTRACTS
→ DEPLOYMENT_AND_OPERATIONS
→ PHASE_STATUS / 当前 implementation 规范
→ 代码、测试、部署脚本、Issue、PR、提示词
```

ADR 只解释重大决策。ADR 中已经批准的结论必须同步反映到对应权威文档；不得只修改 ADR 而让主文档继续保持旧规则。

`PHASE_4_BASELINE.md` 只冻结已经人工确认的产品方向。未明确冻结的 API 字段、数据库表、医学阈值、营养数据源和技术选型仍需后续讨论或 Spike。

## 3. 当前阅读路径

### 理解产品和架构

```text
../README.md
→ PRODUCT_REQUIREMENTS.md
→ SYSTEM_ARCHITECTURE.md
→ DOMAIN_MODEL.md
→ PHASE_4_BASELINE.md
→ STATE_MACHINES.md
→ API_CONTRACTS.md
→ SECURITY_AND_PRIVACY.md
→ DEPLOYMENT_AND_OPERATIONS.md
→ PHASE_STATUS.md
```

### 开始任何代码任务

```text
../AGENTS.md
→ 本 README
→ PHASE_STATUS.md
→ 与任务有关的权威文档
→ 对应 ADR
→ 已批准的 implementation 规范
→ 目标模块 AGENTS.md / README.md
```

没有 `READY` 或 `IN_PROGRESS` 的 Phase/Slice、没有明确 Allowed Paths、没有验收标准时，禁止开始代码实现。

Phase 4 当前为 `DISCOVERY`。即使存在 `PHASE_4_BASELINE.md`，也不得直接实现 Fact、Goal、HealthProgram、训练、恢复、饮食或 Web 用户业务。

## 4. 提示词治理

交给 ChatGPT、Codex、Claude Code、Hermes、Trae 或其他 Agent 的实施提示词必须：

1. 声明目标 Phase 和 Slice。
2. 要求先读取本目录权威文档以及相关 ADR。
3. 列出 `Primary Module`、`Allowed Paths`、`Forbidden Paths`、`Required Verification`、`Out of Scope`。
4. 不得用提示词重新定义产品、架构、状态机、安全边界或 API 合同。
5. 发现文档冲突、缺失合同或无法验证时停止实现并报告，不得自行补全架构。
6. 完成后把实现、测试、真实验收、限制和风险写回 `PHASE_STATUS.md`。
7. Phase 4 的医学阈值、营养数据源或未冻结技术选择不得由实现 Agent自行决定。

## 5. 架构变更流程

冻结后任何架构变化必须执行：

```text
提出变更原因和影响
→ 新增或更新 ADR
→ 更新全部受影响的权威文档
→ 评估兼容、迁移、安全和运维影响
→ 用户人工批准
→ PHASE_STATUS 标记可实施
→ 才能修改代码
```

禁止通过代码提交、数据库迁移、Kubernetes 清单或提示词反向改变架构。

## 6. 当前实现与目标架构

- `health_agent/` 中 Phase 1–2C 的 Python Runtime、Tool Loop、Session、JSON Store、lease/fencing/checkpoint/recovery 和交互式 CLI 是**已实现事实**。
- 它们是未来独立 `health-agent` 服务的迁移基础，但当前仍不是生产部署形态。
- Slice 1 已删除 Java backend 和旧 Compose；Flutter、Vue、Mini Program 与部署目录均按冻结目标重新定位。
- `health_platform/` 在 Phase 3 当前 Slice 中建立生产基础与 Identity；健康业务模块仍未实施。
- Phase 3 收敛生产与权限底座；Phase 4 才开始 Fact、Goal、HealthProgram、训练、恢复、饮食、执行反馈和调整闭环。
- `frontend/` 保持管理端定位；Phase 4 规划独立 `clients/web/` 作为首个用户业务验证入口。

## 7. 文档清理原则

架构冻结删除了已被新体系取代的旧权威文档与完成阶段临时实施规范。历史内容仍可通过 Git 记录追溯，但不再参与当前决策。

2026-07-12 新增 ADR 0023 后，旧 Phase 3D–3J 中涉及健康业务的阶段名称只作为历史路线存在。当前边界以 ADR 0023、`PHASE_4_BASELINE.md` 和 `PHASE_STATUS.md` 为准。

保留历史 ADR 的目的仅是解释决策演进；其状态和替代关系以 [`decisions/README.md`](decisions/README.md) 为准。