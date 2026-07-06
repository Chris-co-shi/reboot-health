# reboot-health

`reboot-health` 是一个由 **Python Health Agent Harness** 驱动、由 **Java Health Domain Kernel** 约束、由 **Flutter** 承载正式体验的 AI-native 个人健康系统。

它不是“健康后台加一个聊天框”，而是围绕个人健康场景建设可控制、可观察、可验证的 Agent 驾驭工程。

本项目不做医学诊断，不替代医生意见。

## 核心架构

```text
Python Health Agent Harness
├── Agent Loop
├── Skills
├── Tool Registry
├── Context Builder
├── Session Runtime
├── Memory
├── Approval
├── Model Router
├── Run Trace
├── Evaluation
└── Recovery

Java Health Domain Kernel
├── Confirmed Facts
├── Deterministic Safety Rules
├── Goal / Constraint / Plan State
├── Device Identity
├── Audit
├── Idempotency
└── Controlled Tools

Flutter Client
└── Natural Language + Action Cards
```

核心关系：

> Python 决定下一步应该做什么；Java 决定什么允许做并可靠保存；Flutter 负责用户如何表达、确认和行动。

## 工程价值

本项目重点不是训练新模型，而是通过 Harness Engineering 让现有模型在健康领域中具备：

- 可版本化 Skill。
- 受控领域工具。
- 最小上下文组装。
- 分级确认策略。
- 长期记忆候选。
- 完整运行轨迹。
- 失败归因和恢复。
- 可重复场景评测。
- 可替换模型 Provider。

项目借鉴通用 Agent Harness 的运行时思想，但不复制开放 Shell、任意文件系统工具或无限自治能力。健康场景中的工具面必须更窄，重要目标、健康约束和计划变化必须遵守确认与安全边界。

## 当前状态

- M1、M2A、M2B：已完成。
- M2.5-A：`IMPLEMENTED_WITH_BLOCKERS`。
- Java 后端与 Python Mock Runtime 已通过自动化测试。
- 当前 Python Runtime 仍是 Harness 技术骨架，尚未实现完整 Agent Loop、Skill Registry、Memory、Approval 和 Evaluation。
- Flutter 源码骨架已存在，但开发环境缺少 Flutter SDK，真实 runner 和四端构建尚未验证。
- M2.5-B、M2.5-C：尚未开始。

交付状态、验收条件和阻塞只以 [`docs/mvp-exec-plan.md`](docs/mvp-exec-plan.md) 为准。

## 仓库结构

```text
agent-runtime/     Python Health Agent Harness，智能与任务编排核心
backend/           Java Health Domain Kernel，事实与安全权威
clients/flutter/   正式 Flutter 客户端
frontend/          冻结的 Vue 内部调试工具
deploy/            Docker Compose 与环境变量示例
docs/              产品、架构、领域、安全和里程碑文档
```

## 最小验证入口

```bash
cd backend && mvn test

cd ../agent-runtime
python3 -m compileall agent_runtime tests
python3 -m unittest discover -s tests

cd ../clients/flutter
flutter pub get
flutter analyze
flutter test

cd ../..
docker compose -f deploy/docker-compose.yml config
```

## 文档入口

- [产品范围](docs/product-scope.md)
- [架构方案](docs/architecture.md)
- [业务领域模型](docs/domain-model.md)
- [API 与数据库](docs/api-db.md)
- [安全规则](docs/safety-rules.md)
- [执行计划与状态](docs/mvp-exec-plan.md)
- [架构决策记录](docs/decisions/)

## Agent 规则

- [全仓规则](AGENTS.md)
- [Python Health Agent Harness](agent-runtime/AGENTS.md)
- [Java Health Domain Kernel](backend/AGENTS.md)
- [Flutter 客户端](clients/flutter/AGENTS.md)
- [Vue 调试工具](frontend/AGENTS.md)
- [部署](deploy/AGENTS.md)
- [文档治理](docs/AGENTS.md)
