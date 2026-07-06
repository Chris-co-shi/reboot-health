# reboot-health

`reboot-health` 是一个个人使用的健康、减脂和体能重建应用，用于把计划、执行记录、趋势分析、AI 建议和用户确认串成安全闭环。

本项目只做健康管理和训练辅助，不做医学诊断，不替代医生意见。AI 只能生成结构化草案或建议，不能直接修改或发布生效计划。

## 当前阶段

当前处于 **M2.5-A：技术与产品骨架**。

代码目标：

- 唯一用户档案。
- 健康约束管理。
- 目标管理。
- M2A 审计追加写。
- 唯一长期 Plan。
- 7 天人工计划草案、复制草案、预览、确认和取消。
- 当前计划按日期查询。
- M2B POST 接口的 `Idempotency-Key` 幂等控制。
- Flutter 主客户端骨架。
- Java 创建并管理 `AgentRun`。
- Python Agent Runtime 使用 Model Mock 返回稳定结构化结果。
- 首台设备 bootstrap 初始化、后续设备配对、设备凭据和安全审计。

不包含：

- 真实云模型调用。
- AI 首次规划访谈。
- 今日执行。
- 周分析。
- 规则引擎。
- 完整登录注册、多用户和 IAM。
- HealthKit / Health Connect。

## 技术栈

后端：Java 21、Spring Boot 3.5.x、Maven、PostgreSQL 17、Flyway、MyBatis-Plus、Testcontainers。

主客户端：Flutter，目标平台为 iOS、Android、macOS、Windows。

内部调试前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、ECharts、pnpm。Vue 已冻结为内部调试工具，不再新增正式业务页面。

Agent Runtime：Python 3.12，默认 Model Mock，不直接连接 PostgreSQL，不直接写业务表。

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

Flutter：

```bash
cd clients/flutter
flutter pub get
flutter analyze
flutter test
```

Python Agent Runtime：

```bash
cd agent-runtime
python3 -m unittest discover -s tests
```

部署配置：

```bash
docker compose -f deploy/docker-compose.yml config
```

## 里程碑状态

- M1：文档和工程骨架，已完成。
- M2A：用户档案、健康约束、目标管理，已完成。
- M2B：计划、计划版本和人工确认，已完成。
- M2.5-A：Flutter、AgentRun、Python Runtime、设备认证骨架，实施中。
- M2.5-B：AI 首次规划闭环，未开始。
- M2.5-C：最小今日执行反馈，未开始。
- M3：正式今日执行和每日数据记录。
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
