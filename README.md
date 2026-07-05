# reboot-health

`reboot-health` 是一个个人使用的健康、减脂和体能重建应用，用于把计划、执行记录、趋势分析、AI 建议和用户确认串成安全闭环。

本项目只做健康管理和训练辅助，不做医学诊断，不替代医生意见。AI 只能生成结构化草案或建议，不能直接修改或发布生效计划。

## 当前阶段

当前处于 **M2A-FIX：仓库治理、持久化重构和 M2A 修复**。

代码目标：

- 唯一用户档案。
- 健康约束管理。
- 目标管理。
- M2A 审计追加写。
- `/plan/setup/*` 基础资料页面。

不包含：

- AI 调用。
- Plan / PlanVersion。
- 今日执行。
- 周分析。
- 规则引擎。
- 登录注册和多用户。

## 技术栈

后端：Java 21、Spring Boot 3.5.x、Maven、PostgreSQL 17、Flyway、MyBatis-Plus、Testcontainers。

前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、ECharts、pnpm。

部署：Docker Compose，应用容器连接宿主机 PostgreSQL 17，远程访问边界由 Tailscale 承担。

## 本地启动和验证

后端：

```bash
cd backend
mvn test
```

前端：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
pnpm run preview -- --host 127.0.0.1 --port 4173
```

部署配置：

```bash
docker compose -f deploy/docker-compose.yml config
```

## 里程碑状态

- M1：文档和工程骨架，已完成。
- M2A：用户档案、健康约束、目标管理，代码验收通过后仍需用户页面人工验收。
- M2B：计划、计划版本和人工确认。
- M3：今日执行和每日数据记录。
- M4：周分析和确定性规则。
- M5：AI 起草及调整建议。
- M6：调整确认和新计划版本。

## 文档入口

- [产品范围](docs/product-scope.md)
- [领域模型](docs/domain-model.md)
- [架构方案](docs/architecture.md)
- [API 与数据库](docs/api-db.md)
- [安全规则](docs/safety-rules.md)
- [MVP 执行计划](docs/mvp-exec-plan.md)
- [未来 AI 调整设计](docs/future/ai-adjustment.md)
- [架构决策记录](docs/decisions/)

## 规则入口

- 全仓规则：`AGENTS.md`
- 后端规则：`backend/AGENTS.md`
- 前端规则：`frontend/AGENTS.md`
