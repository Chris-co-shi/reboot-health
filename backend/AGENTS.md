# 后端 Coding Rules

## Java 21

- 使用 Java 21 正式特性，不使用 preview feature。
- DTO、Command、Query、Response 等不可变数据载体优先使用 `record`。
- `Optional` 只用于返回值，不用于实体字段、DTO 字段和方法参数。
- 业务日期使用 `LocalDate`；创建、更新和审计时间使用 `Instant`。
- 当前时间必须通过注入 `Clock` 获取，避免业务代码散落 `Instant.now()`。
- 禁止字段注入，统一使用构造器注入。
- 不使用静态可变状态；不滥用 `var`。
- 不捕获异常后静默处理，不使用异常作为普通流程控制。
- 不使用魔法字符串表达状态、类型或错误码。

## Lombok

- Lombok 必须使用 Spring Boot 依赖管理，`optional=true`，并配置 Maven annotation processor。
- 允许：`@Getter`、基础设施对象上的 `@Setter`、`@RequiredArgsConstructor`、`@Builder`、`@Slf4j`、框架需要的 `@NoArgsConstructor`、语义明确的 `@AllArgsConstructor`。
- 禁止在领域聚合上使用 `@Data`、类级 `@Setter`、`@SneakyThrows`。
- DTO、Command、Response 可用 `record` 时不使用 Lombok。
- 领域聚合必须通过明确业务方法修改状态，不得通过任意 setter 绕过不变量。

## 注释与 Javadoc

- 新增或修改的 public class/interface/enum 必须有中文类级 Javadoc。
- 领域聚合、Application Service、Repository Port、Controller、Persistence Converter、TypeHandler、关键状态转换、归档方法和非直观 SQL 必须说明职责、边界、不变量和原因。
- 不给 getter/setter 逐个写 Javadoc，不把代码逐句翻译成注释，不保留过期注释。

## 分层与领域规则

依赖方向：

```text
Controller -> Application Service -> Domain -> Repository Port
Persistence Adapter -> Repository Port
```

- Controller 不得依赖 Mapper，不得包含领域状态转换。
- Domain 不得依赖 Spring Web、MyBatis-Plus、数据库 DO 或 Controller。
- Repository Port 位于领域或应用边界，不暴露 MyBatis-Plus。
- Application Service 负责事务编排，Domain 负责业务不变量。
- 不使用 MyBatis-Plus `IService` 或 `ServiceImpl`。
- API Response 不得直接返回 Persistence DO。
- 审计和业务修改必须同事务提交。

## MyBatis-Plus

- `UserProfile`、`HealthConstraint`、`Goal` 使用 Persistence DO + Converter + `BaseMapper<DO>`。
- Persistence DO 使用 `@TableName`，显式输入 UUID 时 `@TableId(type = IdType.INPUT)`。
- 简单 CRUD 使用 `BaseMapper`；查询条件使用 `LambdaQueryWrapper` 或 `LambdaUpdateWrapper`。
- 禁止无必要的 `SELECT *` 自定义 SQL，禁止字符串列名拼装条件。
- 不允许直接把领域对象交给 MyBatis 映射。
- 枚举字段在 Persistence DO 中使用 `String`，Converter 显式 `enum.name()` / `Enum.valueOf()`。
- 业务归档是显式状态机，不使用 `@TableLogic` 替代。
- Flyway 是唯一数据库结构变更入口；已提交执行过的迁移不得修改。
- `audit_log` 的 JSONB 写入可保留专用 SQL，但必须有 Testcontainers 覆盖。

## 测试规范

- 领域状态机使用纯单元测试。
- Application Service 测试业务编排和事务。
- API 使用 MockMvc 集成测试。
- PostgreSQL 路径和 Flyway 迁移使用 Testcontainers。
- 数据库约束必须有失败测试。
- 审计失败必须验证业务回滚。
- 不 Mock 领域对象本身，不删除失败测试来让构建通过。
- 测试名明确表达 Given/When/Then 语义。
- 测试数据不得使用真实姓名、生日、疾病报告或真实个人标识。
