# 架构方案

## 架构目标

- 支持 AI-first 的个人健康与训练闭环。
- 保持单用户私有部署简单。
- 明确 Java、Python、Flutter 和 Vue 的职责。
- 通过纵向切片交付，避免一次跨多个运行时扩展业务。
- 关键状态、安全和确认可审计、可测试、可恢复。

## 系统组件

```text
Flutter Client
    ↓ REST
Java Backend
    ├── PostgreSQL 17
    └── internal HTTP → Python Agent Runtime

Vue Debug Tool ── REST → Java Backend
```

- Flutter：唯一正式用户客户端。
- Java：业务事实、安全、确认、状态、设备认证和 AgentRun 权威系统。
- Python：模型 Provider、编排和结构化候选输出。
- Vue：冻结的内部调试工具。
- PostgreSQL：业务和运行状态持久化。

## 部署拓扑

- 单用户私有部署。
- Backend、Agent Runtime 和 Vue 调试工具使用 Docker Compose。
- PostgreSQL 17 可运行在宿主机或受控环境。
- 默认端口绑定本机地址；远程访问由用户自己的安全网络边界处理。
- M2.5-A 不引入 Redis、消息队列、向量数据库或工作流平台。

详细环境变量和容器配置见 `deploy/`；当前交付状态见 `mvp-exec-plan.md`。

## Java 后端

采用 Java 21、Spring Boot、模块化单体、Flyway、MyBatis-Plus 和 Testcontainers。

依赖方向：

```text
Controller -> Application Service -> Domain -> Repository Port
Persistence Adapter -> Repository Port
External Adapter -> Application Port
```

主要模块：

- `profile`：用户档案和已确认健康约束。
- `goal`：目标唯一事实来源。
- `plan`：长期 Plan 和 7 天 PlanVersion 引擎。
- `agent`：AgentRun 权威状态和 Python 调用边界。
- `device`：设备初始化、配对、认证和撤销。
- `audit`：追加写业务与安全审计。
- `idempotency`：关键写请求的幂等边界。

约束：

- 领域层不依赖 Web、Mapper、Python 或 Flutter。
- 数据库事务中不调用 Python 或其他远程服务。
- Java 不负责 Prompt 内容和客户端展示策略。
- AI 候选必须经结构校验、安全检查和确认边界后才能影响业务事实。
- 已确认计划由现有 PlanVersion 引擎发布，不为 AI 建立并行计划事实源。

## Python Agent Runtime

Python Runtime 是无业务事实所有权的执行器：

- 接收 Java 提交的最小上下文。
- 调用 ModelProvider。
- 返回版本化的结构化候选结果。
- 标准化模型超时、无效输出和内部失败。

禁止：

- 访问 PostgreSQL。
- 直接写 Goal、HealthConstraint、Plan 或 PlanVersion。
- 直接发布计划或更新业务确认状态。
- 自行引入多 Agent 自治。

M2.5-A 使用稳定 Model Mock；真实模型路由属于后续阶段。

## AgentRun 调用链

```text
Flutter 创建 AgentRun
→ Java 短事务保存 CREATED 并返回 202
→ 事务提交后受控执行器调用 Python
→ Java 更新 RUNNING / VALIDATING
→ Java 校验结果
→ READY_FOR_USER_REVIEW 或 FAILED
→ Flutter 轮询读取状态和卡片
```

Java 是 AgentRun 状态唯一权威。Python 调用期间不得持有数据库事务。卡住的运行必须有超时和恢复策略。

## Flutter 客户端

目标平台：iOS、Android、macOS、Windows。

原则：

- 移动端优先，桌面端做适配布局。
- 只调用 Java API。
- 自然语言负责表达和解释，卡片负责行动和确认。
- 不向普通用户展示 UUID、revision、PlanVersion 或内部枚举。
- 设备信息通过统一平台存储抽象管理。
- 平台能力通过适配器隔离。

M2.5-A 的 Flutter 真实 runner 和四端构建尚有环境阻塞，不能视为完整验收。

## Vue 调试工具

Vue 只用于已有 M2A/M2B 数据检查和阻塞性修复：

- 不新增 Agent、Program、Phase、DailyAction 或 Observation 正式页面。
- 不与 Flutter 双重实现新功能。
- 不因调试目的绕过后端认证、状态机或审计。

## 设备认证边界

第一阶段使用私有设备认证，不建设完整 IAM：

- 首台设备由服务端 CLI 生成的一次性初始化码建立。
- 后续设备由已授权设备创建配对会话。
- 每台设备有独立身份和可撤销凭据。
- 不得撤销最后一台活跃可信设备。
- 主设备必须显式转移。
- 除明确白名单外，`/api/v1/**` 默认要求设备身份。

精确 API、数据库表和错误码见 `api-db.md`；安全不变量见 `safety-rules.md`。

## 文档和交付边界

- 产品体验和范围：`product-scope.md`。
- 业务模型：`domain-model.md`。
- 技术合同：`api-db.md`。
- 安全规则：`safety-rules.md`。
- 当前状态和阻塞：`mvp-exec-plan.md`。
- 重大决策：`decisions/`。

架构文档不复制完整字段、SQL、API 请求体或里程碑验收清单。