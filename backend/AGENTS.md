# Java 后端 Agent 规则

## 适用范围

适用于 `backend/`。修改业务包时还必须读取对应模块的 `AGENTS.md`。

后端职责：保存领域事实、执行确定性规则、管理事务、确认、审计、设备认证和 AgentRun 状态。后端不负责 Flutter 展示策略，也不负责 Python Prompt 编排。

## Java 21

- 使用 Java 21 正式特性，不使用 preview feature。
- DTO、Command、Query、Response 等不可变载体优先使用 `record`。
- `Optional` 只用于返回值，不用于实体字段、DTO 字段和方法参数。
- 业务日期使用 `LocalDate`；审计和状态时间使用 `Instant`。
- 当前时间必须通过注入 `Clock` 获取。
- 禁止字段注入和静态可变状态。
- 不捕获异常后静默处理，不用异常代替普通流程控制。
- 状态、类型和错误码不得使用散落魔法字符串。

## 分层和依赖

```text
Controller -> Application Service -> Domain -> Repository Port
Persistence Adapter -> Repository Port
External Adapter -> Application Port
```

- Controller 不得依赖 Mapper，不执行领域状态转换。
- Domain 不依赖 Spring Web、MyBatis、数据库 DO、Python 或 Flutter。
- Repository Port 不暴露 MyBatis-Plus 类型。
- Application Service 负责编排和事务；Domain 保护不变量。
- 不使用 `IService`、`ServiceImpl` 侵入领域。
- API Response 不直接返回 Persistence DO。
- 跨业务模块优先通过明确 Application Port 或只读 Query，不直接调用对方 Mapper。

## 事务、异步和外部调用

- 数据库事务中禁止调用 Python Runtime、云模型或其他远程 HTTP 服务。
- 外部调用必须发生在事务提交后或事务外。
- 异步任务必须使用受控 `TaskExecutor`，不得创建裸线程。
- 异步状态必须有唯一权威、终态、超时和启动恢复策略。
- 审计与对应业务状态变更必须同事务提交。
- 幂等记录、业务结果和审计的原子边界必须明确。

## 安全和认证

- `/api/v1/**` 默认受设备认证保护，公开接口必须显式列入白名单。
- Controller 优先从统一请求上下文取得 `DevicePrincipal`，不得重复解析 Bearer Token。
- 不记录 Authorization Header、明文 code、access token、refresh credential 或健康原文。
- 加密密钥必须来自环境变量；仓库不得存在生产默认密钥。
- 认证、凭据轮换、设备撤销和主设备转移必须审计并有自动化测试。

## MyBatis-Plus 与 Flyway

- Persistence DO 使用 `@TableName`；显式 UUID 使用 `IdType.INPUT`。
- 简单 CRUD 使用 `BaseMapper`；非直观 SQL 必须说明锁和并发语义。
- 领域对象不得直接交给 MyBatis 映射。
- 枚举在 DO 中使用 `String`，Converter 显式转换。
- Flyway 是唯一结构变更入口；已提交迁移不得修改。
- 数据库约束与应用校验互补，关键不变量必须有失败测试。

## Lombok 和注释

- Lombok 仅使用 Spring Boot 依赖管理，并配置 annotation processor。
- 领域聚合禁止 `@Data`、类级 `@Setter`、`@SneakyThrows`。
- public class/interface/enum 必须有中文类级 Javadoc。
- 关键状态转换、锁、恢复逻辑、专用 SQL 必须解释原因和不变量。
- 不给显然代码添加逐句翻译式注释。

## 测试

- 领域状态机：纯单元测试。
- Application Service：业务编排、事务和失败回滚。
- API：MockMvc 集成测试。
- PostgreSQL、Flyway、约束和锁：Testcontainers。
- 外部适配器：合同测试；不得用 Mock 测试冒充真实 Java-Python 合同验证。
- 不 Mock 领域对象本身，不删除失败测试换取构建通过。
- 测试数据不得包含真实个人健康资料。

## 子模块规则

- `agent/AGENTS.md`：Java AgentRun 权威和 Python 调用边界。
- `device/AGENTS.md`：设备认证、配对和凭据。
- `plan/AGENTS.md`：计划版本引擎。
- `profile/AGENTS.md`：档案和健康约束。
- `goal/AGENTS.md`：目标单一事实来源。
- `audit/AGENTS.md`：追加写审计。
- `idempotency/AGENTS.md`：幂等和安全重放。

## 验证

```bash
cd backend
mvn test
```

涉及迁移、锁、状态机、审计、认证或幂等时，必须有对应自动化测试。