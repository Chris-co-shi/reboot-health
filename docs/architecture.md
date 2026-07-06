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
Flutter Client / Tailscale
  -> Backend Container (Spring Boot)
  -> Agent Runtime Container (Python, Model Mock)
  -> Host PostgreSQL 17
```

Vue 前端保留为内部调试工具，默认不作为正式用户客户端继续建设。

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
- `agent`：AgentRun 状态、Python Runtime 调用和结构化结果校验。
- `device`：首台设备 bootstrap、后续设备配对、设备凭据和撤销。

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
- Java 是业务事实、AgentRun、设备确认、安全和状态的唯一权威。
- Python Agent Runtime 不连接 PostgreSQL，不直接写业务表，不发布计划。

### Agent Runtime 边界

M2.5-A 新增独立 `agent-runtime/`：

- Python 3.12 兼容。
- 提供 `GET /health` 和 `POST /internal/v1/agent-runs/execute`。
- 默认 `MockProvider`，不依赖外部网络或真实模型 API Key。
- 返回结构化 DTO，由 Java 校验后保存到 `AgentRun`。
- 仅记录 `runId` 等运行标识，不保存密钥、完整 HTTP Header 或敏感原文。

调用链路：

```text
Flutter -> Java AgentRun API -> Python Agent Runtime -> Java 校验和保存 -> Flutter 轮询读取
```

### 设备认证边界

M2.5-A 增加私有单用户设备认证，不扩展为完整 IAM：

- 首台设备必须由服务端 CLI 生成短时一次性 bootstrap code 后初始化。
- 普通 HTTP 接口不得生成 bootstrap code。
- 服务端只保存 bootstrap code 和 refresh credential 的安全摘要。
- bootstrap code 的有效期、长度和最大失败次数由配置控制，当前默认值只是实现默认配置。
- 每台设备拥有独立 `deviceId` 和独立凭据，可单独撤销。
- 后续设备只能由已授权设备创建 `PairingSession` 后配对。
- 二维码或配对 payload 不携带长期访问令牌。
- 安全审计不得记录明文 code、access token、refresh credential 或完整 Authorization Header。

## 4. 客户端架构

### Flutter 主客户端

技术栈：

- Flutter。
- iOS、Android、macOS、Windows。
- `flutter_secure_storage` 通过 `SecureCredentialStore` 抽象保存设备凭据。

页面：

- 今日。
- 教练。
- 计划。
- 数据。
- 我的。

原则：

- 移动端优先，桌面端做适配布局。
- 教练页只调用 Java，不直接调用 Python。
- “我的”页承载设备初始化、配对和设备列表。
- 不展示 `PlanVersion`、`revision`、`periodRevision` 等内部概念给普通用户。
- 不在日志输出 Idempotency-Key、健康数据或凭据。

### Vue 内部调试工具

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
- M2.5 起冻结为内部调试工具，不新增 Agent、Program、Phase、DailyAction 或 Observation 正式业务页面。

## 5. 数据库架构

数据库使用 PostgreSQL 17。当前 API 和数据库结构见 `docs/api-db.md`。

约束方向：

- Flyway 是唯一数据库结构变更入口。
- 数据库约束和应用校验互补。
- 执行记录必须引用计划版本。
- 当前计划按日期查询 `CONFIRMED` 计划版本，不维护全局 `ACTIVE` 版本状态。
- 审计记录追加写。
- AI 原始响应和校验后的结构化结果分开保存。
- `AgentRun`、`AgentToolCall`、`Device`、`PairingSession` 和 `DeviceCredential` 通过 V6 迁移新增。
- 设备安全凭据只保存摘要，不保存明文令牌。

## 6. 配置策略

配置通过环境变量提供：

- 数据库连接地址、用户名和密码。
- AI 兼容接口地址、API Key 和模型名。
- Python Agent Runtime 地址。
- bootstrap code、pairing code、access token 和 refresh credential 的有效期与长度默认配置。
- 服务端口和安全边界配置。

约束：

- 真实 `.env` 不提交。
- 文档、测试和日志不得输出完整密钥或真实数据库密码。
- 健康数据不得写入普通调试日志。
- M2.5-A 默认 Model Mock，不配置真实模型供应商。

## 7. OPEN 未确认事项

- OPEN: Tailscale 使用 Serve 还是绑定 Tailscale IP。
- OPEN: 是否需要在应用层增加一个极简本地访问口令。
- OPEN: 备份文件保存目录、保留天数和加密方式。
- OPEN: 是否需要在 Windows 上提供一键启动脚本。
