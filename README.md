# reboot-health

`reboot-health` 是一个个人使用的健康、减脂和体能重建应用。它服务于单人、PC 私有部署场景，目标是把训练计划、每日执行、身体指标记录、周分析、AI 调整建议和用户确认串成闭环。

本项目不做医学诊断，不替代医生意见。AI 只能生成结构化建议，不能直接修改或发布生效计划。

## 项目目标

MVP 要跑通以下闭环：

```text
AI 起草或调整计划
-> 用户查看差异、依据和风险
-> 用户确认、部分接受或拒绝
-> 系统创建新的计划版本
-> 今日页展示任务
-> 用户记录执行和身体状态
-> 系统生成周分析
-> 再进入下一轮调整
```

第一版只做 5 个页面：

- 今日
- 当前计划
- 数据记录
- 趋势分析
- 调整确认

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

## 当前启动状态

当前处于 M1 骨架阶段：

- 已有 Spring Boot 后端骨架。
- 已有 Vue 前端骨架和 5 个页面占位。
- 已有 Docker Compose 配置，默认绑定 `127.0.0.1`。
- 已有产品、领域、架构、AI、安全规则和执行计划文档。
- 尚未实现业务表迁移、业务接口、AI 调整业务流和规则引擎。

## 本地验证

后端：

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
```

部署配置：

```bash
docker compose -f deploy/docker-compose.yml config
```

前端预览：

```bash
cd frontend
pnpm run preview -- --host 127.0.0.1 --port 4173
```

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
