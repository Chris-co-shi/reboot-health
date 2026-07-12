# 安全与隐私（FROZEN）

## 1. 安全原则

- 身份、权限、版本、幂等、状态转换、Secret、Sandbox 和审计必须由确定性代码执行。
- Prompt 和模型行为只能作为补充控制，不能成为唯一安全边界。
- 所有请求默认最小权限、最小数据、最短有效期。
- 任何跨用户访问、身份不明、Secret 泄露风险、结果不确定副作用和数据完整性冲突必须 fail-closed。
- 产品不做医学诊断；可能紧急的健康情况必须显著提示联系当地急救或专业人士。

## 2. 身份与权限分层

### Health Platform

负责：

- 最终用户身份和登录。
- 用户级业务权限。
- 管理员角色和管理 API 权限。
- Plan、Fact、Risk、File 和历史纠错的授权。

第一阶段最小角色：

```text
USER
ADMIN_OPERATOR
SERVICE_HEALTH_AGENT
```

其中只有 `USER`、`ADMIN_OPERATOR` 可分配给人类账号；`SERVICE_HEALTH_AGENT` 是独立服务主体。管理员使用管理能力前强制 MFA，且不获得健康业务内容修改或用户确认权限。

未来 RBAC/组织模型不得改变 `userId` 数据归属和服务边界。

### health-agent

不实现用户业务 RBAC，只验证：

- 调用方是受信 Health Platform。
- JWT 与 Task、Run、SubTask、userId 和 Tool scope 匹配。
- 请求未过期、未撤销、未重放。
- Tool、Sandbox 和资源策略允许执行。

## 3. 服务间认证

Health Platform 与 health-agent 使用：

```text
mTLS
+ 短期 JWT
```

mTLS 证明服务身份，JWT 绑定一次 Task 或 Tool 调用的授权上下文。

JWT 最少 claims：

```text
iss
aud
sub
jti
iat
nbf
exp
userId
taskId
runId
subTaskId（可选）
allowedToolScope
contractVersion
```

要求：

- 有效期应短，按任务阶段签发。
- `aud` 必须精确匹配目标服务。
- `jti` 支持撤销和重放检测。
- token 不能被模型、日志、Trace、Checkpoint 或 Tool Result 看到。
- Sub-Agent token 的 `delegationDepth` 固定为 1。

## 4. Tool 安全

ToolDefinition 必须声明：

```text
permission
riskLevel
executionMode
sideEffect
idempotency
compensationPolicy
networkPolicy
filesystemPolicy
secretRefs
timeout
cpu/memory/disk limits
```

Runtime 在执行前验证 Tool 合同，不允许模型扩大权限或修改执行策略。

### 允许在 Worker 内执行

- Health Platform 内部只读 REST Tool。
- 纯计算、确定性、无外部副作用 Tool。
- 已审查、无不可信输入的低风险结构化转换。

### 必须进入 Sandbox

- Shell 或代码执行。
- 用户上传文件解析。
- PDF、图片、压缩包、Office 文档和第三方不可信内容。
- 临时依赖安装。
- 任意外部网络访问。
- 可能接触文件系统或执行器的 Tool。

第一版不一定开放通用 Shell Tool；Sandbox 能力存在不代表模型拥有任意执行权限。

## 5. Sandbox

要求：

- 默认无外部网络。
- 默认只读输入、临时可写工作目录。
- 进程、CPU、内存、磁盘、文件数量和执行时间有限制。
- 运行结束销毁容器和临时卷。
- 禁止挂载宿主机、Kubernetes ServiceAccount Token、Docker/Container runtime socket。
- 禁止访问 PostgreSQL、Redis、MinIO 管理端、Health Platform/health-agent 内部管理端、云元数据和私网未授权地址。

### 网络策略

仅 Tool 策略显式允许的域名/IP/协议/端口可临时访问。

必须防止：

- DNS rebinding。
- 未授权重定向。
- SSRF 到内网、metadata 或管理端。
- 通过代理或 DNS 隧道绕过策略。

## 6. Secret 管理

第一版由 Health Platform 作为 Secret 管理和签发中心，不依赖 Vault，但通过接口保留未来迁移能力。

组件：

```text
SecretService
SecretRepository
KeyEncryptionProvider
IssuancePolicy
SecretAuditLog
```

要求：

- Secret 使用 envelope encryption。
- master key 不保存在业务数据库中，由部署环境或宿主密钥服务提供。
- 支持版本、轮换、停用、撤销和访问审计。
- 管理员可以配置 Secret，但不能重新查看明文。
- health-agent-worker 使用 mTLS + Task JWT 请求临时凭证。
- 优先签发 5–15 分钟的提供商临时 token。
- 固定密钥仅在无法签发临时凭证时短暂进入内存或 tmpfs。
- health-agent-api 原则上无权获取真实 Secret。

注入优先级：

```text
tmpfs 只读文件
→ 文件描述符
→ 短期环境变量
→ 禁止命令行参数
```

不得把 Secret 写入 PostgreSQL 明文字段、Redis、日志、Trace、Checkpoint、模型上下文、Prompt 或 Tool 返回。

## 7. 文件安全

上传流程必须校验：

- 用户和业务用途。
- 文件大小和用户配额。
- MIME、扩展名和实际魔数。
- checksum。
- 恶意文件扫描结果。
- 压缩炸弹、超大页数、嵌入对象和宏风险。

MinIO 管理端不暴露公网。客户端和 Agent 只使用限定对象、方法、大小和有效期的短期签名 URL。

原文件不可被 Agent 覆盖；派生产物使用不同 object key 和版本。

## 8. 文件删除和隐私权

用户可以申请彻底删除原始健康文件。

删除流程：

```text
用户申请
→ 二次确认
→ DELETION_PENDING
→ 立即禁止新下载、解析和召回
→ 删除原文件和所有派生物
→ 删除 RAG Chunk 与向量
→ 清理缓存和 Sandbox 临时副本
→ 校验结果
→ DELETED
```

仅保留不含文件内容的删除审计：文件 ID、申请人、时间、原因、对象数量、结果和校验摘要。

任务正在使用文件时，停止新的文件访问；当前安全步骤结束后终止或清理相关 Run，再完成删除。

## 9. 业务数据确认

- 模型消息、Summary、RAG 结果和 Tool 输出不能直接成为 HealthFact。
- 文件提取结果逐项确认。
- 历史事实纠正需要二次确认。
- Plan 发布需要整体确认和 revision 校验。
- Risk override 必须绑定用户看到的风险版本和最终变更版本。

## 10. 健康风险边界

系统区分：

1. **技术/安全硬阻断**：越权、数据损坏、Secret、跨用户、未知副作用、非法状态转换。
2. **健康风险提醒和确认**：模型或规则识别的未来 Plan 风险，展示证据、严重度和更安全方案；高风险要求二次确认。
3. **紧急提示**：可能需要紧急医疗处理时，显著提示用户联系当地急救或专业人士；不得给出诊断或保证。

用户在知情后可以决定未来 Plan 的非强制性业务选择；系统必须完整记录风险说明和用户选择。法律、监管或产品完整性要求的硬阻断不允许 override。

具体医学阈值必须有可追溯来源和专业审核，未审核项标记 `NEEDS_MEDICAL_REVIEW`，不得由开发者或模型随意填写。

## 11. 数据最小化与保留

### Health Platform

长期保存：

- 用户可见对话（按用户删除和产品政策）。
- 已确认事实、Plan、执行、风险和修订。
- 业务审计。

### health-agent

分级保留：

- 敏感执行上下文：短期。
- 普通 Task/Run/Step 元数据：较长。
- 审计摘要：长期。
- 聚合指标：不包含原始内容，可长期。

Task 完成不删除 Platform 权威事实。Context 压缩只改变模型可见输入，不代表删除源消息。

具体保留天数在部署 Slice 中配置，但必须满足：

- 有配置版本和审计。
- 到期自动清理。
- 删除同步失效 RAG。
- 不因日志方便无限保留敏感数据。

## 12. 日志和可观测性

允许记录：

- traceId/taskId/runId/stepId/toolCallId。
- 脱敏 userId。
- 状态、延迟、次数、错误分类、模型和 Tool 名称。
- token/成本汇总。

禁止记录：

- 完整用户健康原文。
- 完整 Prompt 或隐藏推理。
- raw model response。
- Secret、Token、Authorization header。
- 完整敏感 Tool 返回。
- 文件原文、OCR 全文和签名 URL。

## 13. 管理端安全

- 管理员只能查看完成职责所需的摘要。
- 敏感内容访问采用显式权限、原因记录和审计。
- 管理员不能修改用户 Fact、Plan、RiskAcknowledgement 或 Summary。
- 管理操作必须防 CSRF、重放和越权。
- 高危操作需要二次确认和理由。

## 14. 跨用户隔离测试

生产验收必须包含：

- 使用 user A token 访问 user B Fact、Plan、Task、File 全部失败。
- 使用 Task A delegation token 调用 Task B Tool 失败。
- Sub-Agent 超出 Tool scope 失败。
- 过期、撤销和重放 jti 失败。
- RAG metadata 过滤不会返回其他用户 Chunk。
- 签名 URL 不能访问其他对象或扩大方法。

## 15. 事件和回调安全

- callback 使用 mTLS、JWT 和 `eventId` 幂等。
- payload 使用 hash 校验。
- 事件序列缺口必须对账。
- dead-letter 不能包含 Secret 或完整敏感内容。
- 重放不能绕过当前权限、版本和状态检查。

## 16. 安全变更规则

任何削弱以下边界的变更必须新增 ADR 并由用户批准：

- 服务间认证。
- Tool/Sandbox/网络策略。
- Secret 管理。
- 跨用户隔离。
- 文件删除范围。
- Fact/Plan/Risk 确认。
- 日志脱敏和数据保留。

## 17. Identity 与字段加密基线

- 用户 Access/Refresh Token 为不透明高熵随机值，PostgreSQL 仅保存 SHA-256 哈希；Redis Key 也只使用 Token 哈希。
- Refresh Token 每次轮换并建立 Family；重放撤销整个 Family并记录安全事件。
- OIDC ID Token 与服务 Token 固定 RS256，发布 current/previous `kid` 公钥；私钥来自只读 Kubernetes Secret。
- Authorization Code 必须短期、一次性、精确匹配 Client/Redirect URI，并验证 S256 PKCE、state 和 nonce。
- 密码使用 Argon2id，最少 12 位，支持长密码并拒绝常见/泄露密码。
- TOTP Secret、联系方式和第三方凭据使用版本化 AES-GCM 字段加密；恢复码和安全问题答案只保存哈希。
- RLS 是 Application 授权后的第二道防线，事务级上下文不得泄漏到连接池后续请求。
- Redis 故障回退 PostgreSQL，既不能绕过认证，也不能令所有有效用户无故失效。
