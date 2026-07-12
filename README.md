<div align="center">

# reboot-health

### AI-first health platform and durable agent runtime

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Architecture](https://img.shields.io/badge/Architecture-FROZEN-6C5CE7)
![Phase](https://img.shields.io/badge/Phase-3%20Foundation%20%2F%204%20Discovery-00B894)

</div>

> 本项目不做医学诊断，不替代医生、急救服务、营养师或其他持证专业人士。

## Current status

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A Tool Call Agent Loop：DONE
Phase 2B Runtime state/recovery/JSON safety foundation：DONE_EXPLICIT
Phase 2C Interactive Session：DONE
Phase 3A Architecture Freeze：FROZEN

Phase 3：IN_PROGRESS
- 当前活动 Slice：Health Platform Production Foundation and Identity
- 目标边界：生产基础、Identity、用户归属授权、服务间授权、生产 Agent Runtime 和安全验收

Phase 4：DISCOVERY
- 目标边界：Fact、Goal、HealthProgram、训练、恢复、饮食、执行反馈、调整、风险、提醒和 Web 用户闭环
- 任何 Phase 4 Slice 尚未 READY
```

2026-07-12 已完成架构冻结，并通过 ADR 0023 重划 Phase 3/Phase 4 边界。未来代码、测试、部署和 Agent 提示词必须以 [`docs/`](docs/README.md) 为唯一事实来源。

## Frozen target architecture

```text
Web 用户端 / 微信小程序 / Flutter / Vue Admin
                     ↓
               Health Platform
                     ↓  mTLS + short-lived JWT
                 health-agent
                     ↓
        Model Provider / Tool / Sandbox / RAG / Sub-Agent
```

- **Health Platform**：用户身份、Conversation、Fact、Goal、HealthProgram、Plan、Risk、File、Secret、审计和正式 API 的唯一权威。
- **health-agent**：Task/Run/Step、模型、Tool、Checkpoint、RAG、Sub-Agent、Sandbox 和执行可观测性。
- **PostgreSQL**：业务和执行权威持久化。
- **Redis Streams**：调度和协调加速，不是事实源。
- **MinIO**：第一版 ObjectStorageProvider。
- **Kubernetes**：目标拓扑为 3 Control Plane + 3 Worker VM，全部组件运行在 K8s 内。

客户端顺序：

- `clients/web/`：Phase 4 规划中的首个普通用户验证入口。
- `frontend/`：Vue 3 管理、运维、诊断和审计端。
- `clients/miniapp/`：Web 闭环稳定后的用户入口。
- `clients/flutter/`：Web 闭环稳定后的用户入口。

任何客户端均只访问 Health Platform。

详细规则见 [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md)、[`docs/PRODUCT_REQUIREMENTS.md`](docs/PRODUCT_REQUIREMENTS.md) 和 [`docs/PHASE_4_BASELINE.md`](docs/PHASE_4_BASELINE.md)。

## Current repository structure

| 路径 | 当前真实状态 |
|---|---|
| [`health_platform/`](health_platform/README.md) | Python 模块化单体生产基础与 Identity 正在实施；健康业务尚未实现 |
| [`health_agent/`](health_agent/README.md) | Phase 1–2C 已验证 Runtime；生产 API/Worker 和 PostgreSQL 执行存储尚未实现 |
| `clients/web/` | Phase 4 规划目录；当前尚未创建 |
| [`clients/flutter/`](clients/flutter/README.md) | 正式用户客户端空壳；Phase 4 Web 闭环稳定后接入 |
| [`clients/miniapp/`](clients/miniapp/README.md) | 正式用户客户端目录与边界占位；Phase 4 Web 闭环稳定后接入 |
| [`frontend/`](frontend/README.md) | Vue 3 正式管理端空壳，不承担普通用户健康业务 |
| [`contracts/`](contracts/README.md) | 跨服务可机读合同的未来共享目录 |
| [`deploy/`](deploy/README.md) | Kubernetes 目标目录占位；尚无可运行配置 |

这些骨架和占位目录不代表 Health Platform 健康业务、客户端业务、管理功能或 Kubernetes 部署已经完成。

## Current implemented runtime

当前真实可运行代码仍位于 [`health_agent/`](health_agent/README.md)，已经具备：

- OpenAI-compatible Provider。
- 通用有限轮次 Tool Call Loop。
- ToolRegistry / ToolExecutor。
- `convert_weight_unit`。
- Session Message History。
- JSON Store、CAS、lease、heartbeat、fencing。
- execution checkpoint、stale recovery、orphan maintenance。
- interactive Session CLI。

这些是未来独立 `health-agent` 服务的迁移基础，但当前本地 CLI/JSON Store **不是生产部署形态**。

## Local runtime quick start

```bash
cd health_agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

配置：

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=60
```

运行：

```bash
python3 -m agent.main --user-text "190 斤是多少公斤？请调用工具计算。"
python3 scripts/agent_chat.py
```

验证：

```bash
python3 -m compileall agent tests scripts
python3 -m unittest discover -s tests -v
```

JSON Store 是本地明文，只适合受控开发环境。

## Authoritative documents

| 文档 | 内容 |
|---|---|
| [`docs/PRODUCT_REQUIREMENTS.md`](docs/PRODUCT_REQUIREMENTS.md) | 产品、客户端、Fact、HealthProgram、Plan、风险和文件要求 |
| [`docs/PHASE_4_BASELINE.md`](docs/PHASE_4_BASELINE.md) | 已确认的 Phase 4 产品范围与最终验收方向；当前不是实施规范 |
| [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) | 双服务、异步执行、事件、RAG 和 Sub-Agent |
| [`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md) | 领域模型和数据权威 |
| [`docs/STATE_MACHINES.md`](docs/STATE_MACHINES.md) | 状态和合法转换 |
| [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) | 客户端、Runtime、Tool 和事件合同 |
| [`docs/SECURITY_AND_PRIVACY.md`](docs/SECURITY_AND_PRIVACY.md) | mTLS/JWT、Sandbox、Secret 和隐私 |
| [`docs/DEPLOYMENT_AND_OPERATIONS.md`](docs/DEPLOYMENT_AND_OPERATIONS.md) | 六 VM K8s、灰度、备份和运维 |
| [`docs/PHASE_STATUS.md`](docs/PHASE_STATUS.md) | 已完成证据和后续 Phase |
| [`docs/decisions/`](docs/decisions/README.md) | ADR 与替代关系 |

## Development governance

开始任何代码任务前必须读取 [`AGENTS.md`](AGENTS.md)。

规则摘要：

```text
讨论并形成决策
→ 更新权威文档 / ADR
→ 用户批准
→ Phase/Slice 标记 READY
→ 创建 implementation 规范
→ Codex/人工实现
→ 验证和真实验收
→ 写回 PHASE_STATUS
```

没有 READY Slice 时禁止开始业务代码实现。

## Implementation status

当前活动工作仍属于 Phase 3 的 Health Platform Production Foundation and Identity。生产 SQL Composition Root、完整 OAuth/Identity、权限用例和运行集成仍有缺口。

Phase 4 只完成了产品与阶段治理重基线，状态为 `DISCOVERY`。不得把 `PHASE_4_BASELINE.md` 或目录占位描述成业务已实现。