# Runtime 规则

本目录负责模型调用适配、结构化输入输出和运行编排。

- Java 是业务事实和运行状态的唯一权威。
- 本目录不得访问业务数据库或直接修改业务数据。
- 模型输出只能作为候选返回给 Java 校验。
- 使用 Python 3.12 和明确类型标注。
- Provider 接口与具体实现分离。
- M2.5-A 只使用 MockProvider。
- 不记录完整健康原文或认证信息。
- 未经确认不引入多 Agent 框架、向量数据库或重量工作流依赖。
- 合同变化先定义请求、响应和错误样例，再分别修改两端。

验证：

```bash
python3 -m compileall agent_runtime tests
python3 -m unittest discover -s tests
```
