# 0016 Sandbox、Secret 与文件生命周期

## 状态

已确认，2026-07-12 生效。

## 背景

用户文件、第三方内容、代码执行和外部服务凭证是 health-agent 中风险最高的边界。将长期 Secret 暴露给模型、Worker 数据库或不受限 Sandbox 会导致不可接受的泄露和越权风险。

## 决策

- Tool 通过合同声明 executionMode、网络、文件、Secret、资源、副作用、幂等和补偿策略。
- 文件解析、代码/Shell、不可信第三方内容和受限外网访问必须进入 Sandbox。
- Sandbox 默认无网络、临时文件系统、资源受限，禁止访问宿主机、Kubernetes Token、内部服务、数据库、Redis、MinIO 管理端和云元数据。
- Health Platform 是第一版 Secret 管理和签发中心，使用 envelope encryption、版本、轮换、撤销和访问审计。
- health-agent-worker 只能以 Task/Run/Tool 绑定的短期授权获取临时凭证；模型和 health-agent-api 不得看到真实 Secret。
- 文件通过 ObjectStorageProvider 管理，第一版实现 MinIO。
- 用户可以申请彻底删除文件，删除原件、派生物、OCR、RAG、向量、缓存和临时副本，只保留不含内容的删除审计。
- 文件提取的健康字段逐项确认后才成为正式 Fact。

## 影响

正面：

- 将高风险执行与业务服务隔离。
- Secret 不进入模型上下文和持久执行状态。
- 文件生命周期具备完整隐私删除闭环。

成本：

- 需要 Sandbox 调度、NetworkPolicy、扫描、对象对账和 SecretService。
- 删除需要跨 PostgreSQL、MinIO、RAG 和缓存协调。

## 约束

- Secret 注入优先 tmpfs/文件描述符，不使用命令行参数。
- MinIO 长期 Access Key 不下发给客户端或 Agent。
- Sandbox 能力存在不等于开放任意 Shell Tool。
- 删除失败必须持续告警和重试，不得恢复为普通可用状态。
