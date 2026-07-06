# Java Agent 模块规则

## 职责

本模块负责 Java 侧 AgentRun 权威状态、Python Runtime 调用适配、结构化输出校验、失败映射、审计、超时和恢复。

## 必须遵守

- Java 是 AgentRun 唯一状态权威。
- 创建 AgentRun 使用短事务；Python 调用必须发生在提交后。
- Python 返回内容先做结构校验，再保存为候选输出。
- M2.5-A 不存在 `APPLIED`，不得执行计划发布或业务确认。
- 所有失败信息必须脱敏，不能保存完整 Prompt、Header、密钥或健康原文。
- 幂等重放不得重复触发 Python、重复创建 AgentRun 或重复审计。
- 异步执行必须有受控线程池、终态、超时和启动恢复。

## 禁止

- 不连接或绕过 Repository 直接执行任意 SQL。
- 不在本模块实现 Prompt 业务内容或模型供应商 SDK。
- 不直接写 Goal、HealthConstraint、Plan 或 PlanVersion。
- 不把模型输出当成领域事实。
- 不引入多 Agent 框架、消息队列、向量数据库或工作流平台，除非有单独已确认决策。
- 不修改 Flutter 或 Python 代码作为本模块任务的顺带工作。

## 合同

Java 与 Python 的请求、响应、错误码和 Schema 必须显式版本化。合同变化先更新文档或测试样例，再分别实施两端。

## 验证

- AgentRun 状态机单元测试。
- 异步创建、幂等、超时和恢复集成测试。
- Java HTTP Client 到真实 Python Mock Runtime 的合同测试。
- Python 调用期间不得持有数据库事务。