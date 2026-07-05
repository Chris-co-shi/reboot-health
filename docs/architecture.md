# 架构方案

## 1. 架构目标

- 快速落地个人使用 MVP。
- 保持部署简单。
- 明确领域边界和安全不变量。
- 支持后续按里程碑纵向切片交付。

## 2. 部署环境

- 使用者：单人。
- 运行方式：Docker。
- 数据库：宿主机 PostgreSQL 17。
- 访问方式：本机端口绑定配合 Tailscale。
- Redis：MVP 暂不接入业务流程。

```text
Browser / Tailscale
  -> Frontend Container (Vue + Nginx)
  -> Backend Container (Spring Boot)
  -> Host PostgreSQL 17
```

默认端口绑定 `127.0.0.1`，避免误暴露到公网或局域网。

## 3. 后端架构

技术栈：

- Java 21。
- Spring Boot 3.5.x。
- Maven。
- PostgreSQL 17。
- Flyway。
- MyBatis-Plus。
- Testcontainers。

架构模式：

- 模块化单体。
- REST API。
- 传统事务模型。
- 领域聚合保护关键状态转换。

模块边界：

- `profile`：个人档案与健康约束。
- `goal`：目标管理。
- `plan`：计划和计划版本。
- `execution`：每日执行。
- `metrics`：身体指标和症状记录。
- `analysis`：周期分析。
- `rules`：确定性安全规则。
- `ai`：OpenAI 兼容接口适配。
- `adjustment`：调整建议与用户确认。
- `audit`：审计记录。

依赖方向：

```text
Controller -> Application Service -> Domain -> Repository Port
Persistence Adapter -> Repository Port
```

约束：

- 领域层不得依赖数据库 Mapper、Persistence DO、Web Controller 或 AI 客户端。
- AI 适配器不得直接创建生效计划。
- 计划版本创建必须由领域服务完成。
- 审计和业务修改必须在同一事务内提交。
- M2B 的关键 POST 使用 `Idempotency-Key`，幂等记录、业务修改和审计必须同事务提交。

## 4. 前端架构

技术栈：

- Vue 3。
- TypeScript。
- Vite。
- Pinia。
- Vue Router。
- Element Plus。
- ECharts。
- pnpm。

页面：

- `/today`
- `/plan`
- `/records`
- `/trends`
- `/adjustments`

前端原则：

- 工具型界面，优先清晰和低录入负担。
- 不做营销式首页。
- 不使用复杂权限状态。
- API 调用统一经过 services 层。
- 枚举值与中文显示文本分离。

## 5. 数据库架构

数据库使用 PostgreSQL 17。当前 API 和数据库结构见 `docs/api-db.md`。

约束方向：

- Flyway 是唯一数据库结构变更入口。
- 数据库约束和应用校验互补。
- 执行记录必须引用计划版本。
- 当前计划按日期查询 `CONFIRMED` 计划版本，不维护全局 `ACTIVE` 版本状态。
- 审计记录追加写。
- AI 原始响应和校验后的结构化结果分开保存。

## 6. 配置策略

配置通过环境变量提供：

- 数据库连接地址、用户名和密码。
- AI 兼容接口地址、API Key 和模型名。
- 服务端口和安全边界配置。

约束：

- 真实 `.env` 不提交。
- 文档、测试和日志不得输出完整密钥或真实数据库密码。
- 健康数据不得写入普通调试日志。

## 7. OPEN 未确认事项

- OPEN: Tailscale 使用 Serve 还是绑定 Tailscale IP。
- OPEN: 是否需要在应用层增加一个极简本地访问口令。
- OPEN: 备份文件保存目录、保留天数和加密方式。
- OPEN: 是否需要在 Windows 上提供一键启动脚本。
