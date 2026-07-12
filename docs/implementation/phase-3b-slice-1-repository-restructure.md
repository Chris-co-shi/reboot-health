# Phase 3B Slice 1：Repository Restructure and Legacy Removal

## 状态

`DONE`

## 目标

以 Phase 3A 冻结架构为唯一事实来源，删除旧 Java 正式后端和旧部署链路，建立 Python Health Platform、跨服务合同、微信小程序和 Kubernetes 部署目标目录，并把 Flutter、Vue 与 health-agent 重新定位到冻结架构中的职责。

## 冻结架构依据

- [`../PRODUCT_REQUIREMENTS.md`](../PRODUCT_REQUIREMENTS.md)
- [`../SYSTEM_ARCHITECTURE.md`](../SYSTEM_ARCHITECTURE.md)
- [`../DOMAIN_MODEL.md`](../DOMAIN_MODEL.md)
- [`../STATE_MACHINES.md`](../STATE_MACHINES.md)
- [`../API_CONTRACTS.md`](../API_CONTRACTS.md)
- [`../SECURITY_AND_PRIVACY.md`](../SECURITY_AND_PRIVACY.md)
- [`../DEPLOYMENT_AND_OPERATIONS.md`](../DEPLOYMENT_AND_OPERATIONS.md)
- ADR 0012–0017

## 删除范围

- `backend/**` 全部 Java、Maven、Flyway 和旧 Java/Python 调用链。
- Flutter 中设备 bootstrap、pairing、旧 Java credential、AgentRun 和 M2.5-A 业务实现。
- Vue 中 M2A/M2B 页面、Java API client、旧 DTO、代理和调试工具定位。
- `deploy/` 中旧 Docker Compose、旧端口、环境变量和 Java/Python/Vue 联合启动配置。

删除前审计确认：旧实现中的 revision、幂等、审计、状态转换、时区有效性和历史不可变等仍有效语义，已经由冻结权威文档覆盖；未发现需要补入冻结文档的新领域不变量。

## 保留范围

- `health_agent/agent/**`、`health_agent/tests/**` 及 Phase 1–2C 已验证行为。
- Flutter 工程配置、通用主题和最小应用壳。
- Vue 3、TypeScript、pnpm 和通用构建配置。
- 冻结权威文档和 ADR。

## 目标目录

```text
health_platform/
health_agent/
clients/flutter/
clients/miniapp/
frontend/
contracts/schemas/
deploy/{kubernetes,helm,environments,observability}/
docs/
```

## Allowed Paths

```text
.gitignore
README.md
AGENTS.md
backend/**
health_platform/**
health_agent/README.md
health_agent/AGENTS.md
health_agent/pyproject.toml
health_agent/**/*.md
clients/flutter/**
clients/miniapp/**
frontend/**
contracts/**
deploy/**
docs/PHASE_STATUS.md
docs/implementation/README.md
docs/implementation/phase-3b-slice-1-repository-restructure.md
```

仅当删除 Java 后确有引用需要修复时，允许最小修改 `.github/**` 或根目录构建/检查脚本，并在完成记录中逐项说明。

## Forbidden Paths

- `health_agent/agent/**`
- `health_agent/tests/**`
- 除本规范 Allowed Paths 外的冻结权威文档与 ADR

## Forbidden Changes

- 不改变冻结架构、服务边界、状态机、安全或 API 语义。
- 不实现 Health Platform 业务、Web 框架、数据库、REST API、Redis Streams、MinIO、RAG、Sub-Agent 或 Sandbox。
- 不重写 Runtime，不删除或放宽 Phase 1–2C 测试。
- 不创建虚假的 Kubernetes Manifest、Helm Chart 或生产可运行声明。

## 合同变化

不改变冻结 API 合同，不生成完整 OpenAPI。新增 `contracts/` 仅定义跨服务合同的唯一存放职责、版本和兼容原则，语义继续以 `docs/API_CONTRACTS.md` 为权威。

## 迁移兼容策略

- 旧 Java 后端、设备认证、AgentRun API 和 Compose 链路不提供运行期兼容层，依靠 Git 历史追溯。
- Flutter 和 Vue 仅保留可构建壳，不提前接入尚未实现的 Health Platform API。
- health-agent Phase 1–2C 原有代码、测试和恢复语义原样保留。
- 后续合同演进采用版本化和 Expand–Migrate–Contract；本 Slice 不落地具体 Schema。

## 验证方式

- 仓库结构、`git diff --check`、变更范围和旧引用扫描。
- Java/pom 清理扫描。
- health-agent 全量及专项回归。
- Health Platform `compileall` 和单元测试发现。
- Flutter `pub get`、`analyze`、`test`（环境可用时）。
- Vue `pnpm install --frozen-lockfile`、`typecheck`、`build`。

## Definition of Done

- 附件任务中 Phase 3B Slice 1 的全部 Definition of Done 项满足。
- 所有实际验证结果、未验证项和风险写回本文件及 `PHASE_STATUS.md`。
- Slice 标记 `DONE`，Phase 3B 保持 `IN_PROGRESS`。

## Out of Scope

- Phase 3C–3J 的业务、数据、API、基础设施和生产验收实现。
- Web/客户端技术选型之外的新框架或依赖。
- 提交、推送和创建 PR。

## 实际完成记录

- 完整删除 `backend/`、Maven、Java、Flyway 和旧 Java/Python 调用链；删除前审计未发现冻结文档遗漏的有效领域不变量。
- 新增框架无关 `health_platform/` Python 包骨架，未选择 Web 框架或实现业务 Schema/API。
- 保留 `health_agent/agent/**` 和 `health_agent/tests/**`，仅修正文档与系统边界提示词中的旧定位。
- Flutter 删除设备认证、AgentRun、Java DTO/API 和 M2.5-A 业务代码，保留工程并建立最小客户端空壳。
- Vue 删除 M2A/M2B 页面、DTO、Java API client 和本地代理，建立最小 Vue 3 Admin Shell。
- 新增 `clients/miniapp/`、`contracts/` 和 Kubernetes 目标部署占位结构。
- 删除旧 Docker Compose、旧环境示例和前端旧容器配置；未创建虚假 Manifest 或 Helm Chart。
- 更新根 README、Agent 规则、`.gitignore`、implementation 索引与 Phase 状态。

实际验证：

```text
health-agent compileall：通过
health-agent unittest discover：376 通过，2 个显式真实 LLM 测试跳过
JSON Store multiprocess：4 通过
run lease multiprocess：2 通过
stale recovery：7 通过
orphan pending actions：7 通过
Health Platform compileall：通过
Health Platform unittest discover：0 项（当前骨架无测试）
Flutter pub get：通过
Flutter analyze：通过，无问题
Flutter test：1 通过（移除本机代理对 localhost 的影响后）
Vue pnpm install --frozen-lockfile：通过
Vue typecheck：通过
Vue build：通过
git diff --check：通过
Java/pom 与旧架构引用扫描：通过
Allowed Paths 检查：通过，未越界
```

未执行真实 LLM、Kubernetes、数据库、Redis、MinIO 或端到端业务验收；这些均不属于本 Slice。

## 已知限制

- Health Platform、客户端业务、Admin 功能和部署配置仍未实现，目录与界面仅为骨架或占位。
- Kubernetes 发行版、CNI、Ingress、证书、PostgreSQL Operator 和 Redis 拓扑仍需后续技术 Spike/ADR。
- 当前 `health-agent` 仍使用本地 CLI/JSON Store，不是生产 API/Worker 形态。
