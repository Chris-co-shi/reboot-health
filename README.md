# reboot-health

`reboot-health` 是一个个人使用的健康、减脂和体能重建应用，用于把计划、执行记录、趋势分析、AI 建议和用户确认串成安全闭环。

本项目不做医学诊断，不替代医生意见。AI 只能生成结构化建议，不能直接修改或发布生效计划。

## 当前阶段

当前处于 **M2A：用户档案、健康约束、目标管理**，本地实现已完成，等待人工验收。

已完成：

- M1 文档和工程骨架。
- Spring Boot 后端骨架。
- Vue 前端骨架。
- Docker Compose 配置。
- M2A 后端 API、Flyway 迁移、审计写入和关键测试。
- M2A 前端 `/plan/setup/*` 二级页面。

M2A 目标：

- 唯一用户档案。
- 健康约束管理。
- 目标管理。
- 基础资料页接入 `/plan/setup/*`。

M2A 不包含：

- AI 调用。
- Plan / PlanVersion。
- 今日执行。
- 周分析。
- 规则引擎。
- 登录注册和多用户。

## 技术栈

后端：

- Java 21
- Spring Boot 3.5.x
- Maven
- PostgreSQL 17
- Flyway
- MyBatis-Plus
- Testcontainers

前端：

- Vue 3
- TypeScript
- Vite
- Pinia
- Vue Router
- Element Plus
- ECharts
- pnpm

部署：

- Windows 10 + Docker
- 应用容器连接宿主机 PostgreSQL 17
- Tailscale 负责远程访问边界
- Redis 暂不接入 MVP 业务流程

## 本地启动和验证

后端测试：

```bash
cd backend
/Users/sxc/Documents/tool/apache-maven-3.9.0/bin/mvn test
```

前端：

```bash
cd frontend
pnpm install
pnpm run typecheck
pnpm run build
pnpm run preview -- --host 127.0.0.1 --port 4173
```

部署配置校验：

```bash
docker compose -f deploy/docker-compose.yml config
```

## 里程碑

- M1：文档和工程骨架，已完成。
- M2A：用户档案、健康约束、目标管理，待验收。
- M2B：计划、计划版本和人工确认。
- M3：今日执行和每日数据记录。
- M4：周分析和确定性规则。
- M5：AI 起草及调整建议。
- M6：调整确认和新计划版本。

## 文档入口

- [产品范围](docs/product-scope.md)
- [领域模型](docs/domain-model.md)
- [架构方案](docs/architecture.md)
- [AI 调整设计](docs/ai-adjustment-design.md)
- [安全规则](docs/safety-rules.md)
- [MVP 执行计划](docs/mvp-exec-plan.md)
- [架构决策记录](docs/decisions/)
- [API 与数据库草案](docs/api-db-draft.md)

## 未确认事项

所有尚未确认的事项都在对应文档中以 `OPEN` 标记。实现前不得把 `OPEN` 项自行视为已确认。
