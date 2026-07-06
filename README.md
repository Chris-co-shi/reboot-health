# reboot-health

`reboot-health` 是一个 AI-first 的个人健康、减脂和规律训练辅助系统。AI 负责理解、生成候选和解释；Java 负责事实、安全、确认和状态；Flutter 负责正式用户体验。

本项目不做医学诊断，不替代医生意见。

## 当前状态

- M1、M2A、M2B：已完成。
- M2.5-A：`IMPLEMENTED_WITH_BLOCKERS`。
- Java 后端与 Python Mock Runtime 已通过自动化测试。
- Flutter 源码骨架已存在，但开发环境缺少 Flutter SDK，真实 runner 和四端构建尚未验证。
- M2.5-B、M2.5-C：尚未开始。

交付状态、验收条件和阻塞只以 [`docs/mvp-exec-plan.md`](docs/mvp-exec-plan.md) 为准。

## 仓库结构

```text
backend/           Java 21 / Spring Boot 权威后端
agent-runtime/     Python Agent Runtime，M2.5-A 使用 Model Mock
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
- [Java 后端](backend/AGENTS.md)
- [Python Runtime](agent-runtime/AGENTS.md)
- [Flutter 客户端](clients/flutter/AGENTS.md)
- [Vue 调试工具](frontend/AGENTS.md)
- [部署](deploy/AGENTS.md)
- [文档治理](docs/AGENTS.md)
