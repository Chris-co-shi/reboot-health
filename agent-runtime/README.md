# Agent Runtime

M2.5-A 的 Python Agent Runtime 只提供技术链路验证：

- `GET /health`
- `POST /internal/v1/agent-runs/execute`

当前默认使用可重复的 Model Mock，不接入真实云模型，不访问 PostgreSQL，不直接写业务表。

## 本地运行

```bash
python3 -m agent_runtime.server --host 127.0.0.1 --port 8090
```

## 验证

```bash
python3 -m compileall agent_runtime tests
python3 -m unittest discover -s tests
```
