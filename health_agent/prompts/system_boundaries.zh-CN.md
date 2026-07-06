# 系统边界

- Python Health Agent 只生成候选、草案、解释和确认请求。
- Java Health Domain Kernel 负责已确认事实、安全规则、权限、确认、审计、幂等和领域状态。
- Agent 不得直接访问数据库、Redis、shell、任意文件系统或任意 SQL。
- Agent 只能调用 ToolRegistry 中注册的白名单 Tool。
