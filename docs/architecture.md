# 架构方案

## 1. 架构目标

- 快速落地个人使用 MVP。
- 保持部署简单。
- 明确领域边界和安全不变量。
- 支持后续按里程碑纵向切片交付。

## 2. 已确认部署环境

- 使用者：单人。
- 目标机器：用户 PC 台式机。
- 操作系统：Windows 10。
- 运行方式：Docker。
- 数据库：宿主机 PostgreSQL 17。
- 访问方式：Tailscale。
- Redis：已安装，但 MVP 暂不接入业务流程。

## 3. 总体架构

```text
Browser / Tailscale
  -> Frontend Container (Vue + Nginx)
  -> Backend Container (Spring Boot)
  -> Host PostgreSQL 17
```

默认端口绑定 `127.0.0.1`，避免误暴露到公网或局域网。

## 4. 后端架构

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
- 领域服务保护关键状态转换。

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
Infrastructure Adapter -> Repository Port
AI Adapter -> AI Port
```

约束：

- 领域层不得依赖 AI 客户端、数据库 Mapper 或 Web Controller。
- AI 适配器不得直接创建生效计划。
- 计划版本创建必须由领域服务完成。

## 5. 前端架构

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
- 关键操作必须展示前后差异、风险和确认状态。

## 6. 数据库架构

数据库使用 PostgreSQL 17。

MVP 核心表草案见 `docs/api-db-draft.md`。

约束方向：

- 计划版本状态需要数据库约束配合领域服务保证。
- 执行记录必须引用计划版本。
- 审计记录追加写。
- AI 原始响应和校验后的结构化结果分开保存。

## 7. 配置策略

环境变量：

- `SPRING_DATASOURCE_URL`
- `SPRING_DATASOURCE_USERNAME`
- `SPRING_DATASOURCE_PASSWORD`
- `APP_AI_BASE_URL`
- `APP_AI_API_KEY`
- `APP_AI_MODEL`

密钥约束：

- API Key 不写入代码仓库。
- `deploy/.env` 不提交。
- 文档和日志不得输出完整 API Key。

## 8. 安全边界

- 应用层暂不做账号体系。
- Tailscale 和本机端口绑定承担访问边界。
- 默认 Compose 绑定 `127.0.0.1`。
- 健康数据不得写入普通调试日志。
- 医疗相关输出不得生成诊断结论。

## 9. OPEN 未确认事项

- OPEN: PostgreSQL 数据库名、用户名和密码是否使用当前样例值。
- OPEN: Tailscale 使用 Serve 还是绑定 Tailscale IP。
- OPEN: 是否需要在应用层增加一个极简本地访问口令。
- OPEN: 备份文件保存目录、保留天数和加密方式。
- OPEN: 是否需要在 Windows 上提供一键启动脚本。
