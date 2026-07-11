# API 合同（FROZEN）

## 1. 通用规则

- 外部 API 统一由 Health Platform 提供。
- health-agent 只暴露内部 API。
- 所有 JSON 使用 UTF-8、ISO-8601/RFC3339 时间和显式版本字段。
- 所有资源 ID 使用不透明 ID，不向客户端暴露数据库自增语义。
- 高影响写入必须使用 `Idempotency-Key` 和 `expectedRevision`。
- 错误返回稳定 `code`，不得把 Python traceback、SQL、Prompt 或内部地址暴露给客户端。

统一响应：

```json
{
  "requestId": "req_xxx",
  "traceId": "trace_xxx",
  "data": {},
  "error": null
}
```

失败：

```json
{
  "requestId": "req_xxx",
  "traceId": "trace_xxx",
  "data": null,
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "数据已更新，请刷新后重试。",
    "details": {}
  }
}
```

## 2. API 命名空间

```text
/api/miniapp/**      小程序和 Flutter 业务 API
/api/admin/**        Vue 管理端 API
/internal/agent/**   Health Platform 提供给 health-agent 的 Tool API
/internal/runtime/** health-agent 提供给 Health Platform 的执行 API
```

生产环境不得通过同一公网入口暴露 `/internal/**`。

## 3. 客户端业务 API

以下路径定义资源边界，具体字段在对应实施 Slice 中补充 OpenAPI，但不得改变语义。

### Conversation 和消息

```http
POST /api/miniapp/sessions
GET  /api/miniapp/sessions/{sessionId}
GET  /api/miniapp/sessions/{sessionId}/messages
POST /api/miniapp/sessions/{sessionId}/messages
GET  /api/miniapp/tasks/{taskId}
POST /api/miniapp/tasks/{taskId}/terminate
GET  /api/miniapp/tasks/{taskId}/events
```

提交消息成功即表示消息和 Task 已持久化，不表示 Agent 已完成。

`POST /messages` 请求至少包含：

```json
{
  "clientMessageId": "client_msg_xxx",
  "content": "用户原始消息",
  "expectedSessionRevision": 12
}
```

返回：

```json
{
  "messageId": "msg_xxx",
  "taskId": "task_xxx",
  "taskStatus": "QUEUED",
  "sessionRevision": 13
}
```

### SSE

```http
GET /api/miniapp/tasks/{taskId}/events?afterSequence=123
Accept: text/event-stream
```

事件类型至少包括：

```text
task.snapshot
run.started
progress.changed
waiting.user_input
waiting.confirmation
candidate.plan_ready
risk.opened
run.completed
run.failed
run.terminated
```

SSE 只负责实时体验，不是唯一状态来源。断线后客户端先查询 Task Snapshot，再从最后 sequence 续订。

### Fact 候选和纠正

```http
GET  /api/miniapp/fact-candidates?taskId=
POST /api/miniapp/fact-candidates/{candidateId}/confirm
POST /api/miniapp/fact-candidates/{candidateId}/reject
POST /api/miniapp/facts/{factId}/corrections
POST /api/miniapp/fact-corrections/{correctionId}/confirm
```

所有文件提取候选必须逐项调用确认或拒绝接口。

### Plan

```http
GET  /api/miniapp/plans/current
GET  /api/miniapp/plan-versions/{versionId}
POST /api/miniapp/plan-versions/{versionId}/confirm
POST /api/miniapp/plan-versions/{versionId}/reject
POST /api/miniapp/plan-versions/{versionId}/edits
POST /api/miniapp/plans/{planId}/revisions
```

确认请求：

```json
{
  "expectedRevision": 4,
  "expectedFactVersions": {
    "fact_x": 3
  },
  "riskAcknowledgementIds": ["ack_x"]
}
```

revision 或事实版本不匹配返回 `VERSION_CONFLICT`，不能自动使用客户端旧内容覆盖服务器状态。

### 风险

```http
GET  /api/miniapp/risks/{riskId}
POST /api/miniapp/risks/{riskId}/acknowledge
POST /api/miniapp/risks/{riskId}/decisions
```

决定必须绑定展示内容版本和目标变更 revision。

### 文件

```http
POST /api/miniapp/files/upload-requests
POST /api/miniapp/files/{fileId}/complete-upload
GET  /api/miniapp/files/{fileId}
POST /api/miniapp/files/{fileId}/deletion-requests
POST /api/miniapp/file-deletions/{requestId}/confirm
```

上传申请返回限定对象、大小、类型和有效期的签名 URL。客户端不能获得 MinIO 长期凭证。

## 4. Health Platform → health-agent Runtime API

所有请求使用 mTLS 和短期 JWT。

### 创建 Task

```http
POST /internal/runtime/v1/tasks
Idempotency-Key: <platformTaskId>
```

```json
{
  "platformTaskId": "ptask_x",
  "sessionId": "session_x",
  "userId": "user_x",
  "messageId": "msg_x",
  "userMessage": "...",
  "delegationToken": "short-lived-token",
  "traceId": "trace_x",
  "contractVersion": 1
}
```

返回：

```json
{
  "taskId": "task_x",
  "runId": "run_x",
  "status": "QUEUED",
  "acceptedAt": "2026-07-12T00:00:00Z"
}
```

相同 `platformTaskId` 和相同请求哈希返回第一次结果；请求内容不同返回 `IDEMPOTENCY_KEY_REUSED`。

### 追加用户输入

```http
POST /internal/runtime/v1/tasks/{taskId}/inputs
```

```json
{
  "messageId": "msg_y",
  "messageSequence": 24,
  "content": "...",
  "delegationToken": "...",
  "traceId": "trace_x"
}
```

### 终止 Run

```http
POST /internal/runtime/v1/tasks/{taskId}/runs/{runId}/terminate
```

请求包含 `expectedRunVersion` 和原因。返回 `TERMINATION_REQUESTED`，不能伪造即时终止。

### 查询与对账

```http
GET /internal/runtime/v1/tasks/{taskId}
GET /internal/runtime/v1/tasks/{taskId}/events?afterSequence=
GET /internal/runtime/v1/tasks/{taskId}/snapshot
POST /internal/runtime/v1/tasks/{taskId}/runs
```

最后一个接口仅用于批准重试、恢复或追加预算后创建新 Run。

## 5. health-agent → Health Platform Tool API

### 认证和授权

每次调用必须携带：

- mTLS 服务身份。
- task/run/subTask 绑定短期 JWT。
- `traceId` 和 `toolCallId`。
- Tool 名称和合同版本。

Platform 必须实时校验：

- issuer、audience、expiry、jti。
- taskId、runId、subTaskId、userId。
- Tool scope。
- 数据归属和当前业务状态。
- token 是否撤销或已消费。

### Read Tool

示例路径：

```http
GET /internal/agent/v1/users/{userId}/profile
GET /internal/agent/v1/users/{userId}/facts?types=&asOf=
GET /internal/agent/v1/users/{userId}/plans/current
GET /internal/agent/v1/users/{userId}/executions?from=&to=
GET /internal/agent/v1/users/{userId}/files/{fileId}/download-ticket
```

返回必须包含：

```json
{
  "data": {},
  "sourceRef": "fact_x",
  "contentVersion": 7,
  "validUntil": null,
  "sensitivity": "HEALTH_SENSITIVE"
}
```

### Write Candidate Tool

允许：

```http
POST /internal/agent/v1/users/{userId}/fact-candidates
POST /internal/agent/v1/users/{userId}/plan-candidates
POST /internal/agent/v1/users/{userId}/risk-findings
POST /internal/agent/v1/users/{userId}/correction-requests
POST /internal/agent/v1/users/{userId}/change-requests
```

禁止 Tool API：

- 直接把 Plan 设为 CONFIRMED。
- 直接把 FactCandidate 设为 CONFIRMED。
- 代替用户写 RiskAcknowledgement。
- 直接删除业务审计。
- 直接更新数据库任意字段。

## 6. Runtime Event Callback

```http
POST /internal/agent/v1/runtime-events
Idempotency-Key: <eventId>
```

事件合同：

```json
{
  "eventId": "evt_x",
  "taskId": "task_x",
  "runId": "run_x",
  "sequence": 42,
  "eventType": "RUN_WAITING_USER_INPUT",
  "occurredAt": "2026-07-12T00:00:00Z",
  "payloadVersion": 1,
  "payload": {},
  "payloadHash": "sha256:...",
  "traceId": "trace_x"
}
```

Platform 响应：

```json
{
  "accepted": true,
  "lastAppliedSequence": 42,
  "gapDetected": false
}
```

若 `sequence` 不连续，Platform 仍可幂等记录事件，但必须返回 `gapDetected=true` 并启动 pull/reconciliation。

## 7. 管理 API

```http
GET  /api/admin/tasks
GET  /api/admin/tasks/{taskId}
GET  /api/admin/runs/{runId}/trace
POST /api/admin/runs/{runId}/retry
POST /api/admin/runs/{runId}/recover
POST /api/admin/runs/{runId}/terminate
POST /api/admin/outbox/{eventId}/replay
GET  /api/admin/alerts
```

所有操作请求必须包含原因，并记录审计。管理 API 不能修改 Fact、Plan 内容或用户确认。

## 8. 版本和兼容

- URL 主版本使用 `/v1/`。
- payload 内包含 `contractVersion` 或 `payloadVersion`。
- 灰度期间新旧应用必须同时支持当前和前一兼容版本。
- 删除字段采用 Expand–Migrate–Contract，不允许一步删除。
- 未识别的可选字段忽略；未识别的枚举值不得默认为安全值，必须显式失败或降级。

## 9. 幂等

必须使用幂等键：

- 创建 Agent Task。
- Plan 确认、拒绝和 Revision。
- Fact 确认和历史纠正确认。
- 风险决定。
- 文件删除确认。
- Runtime Event Callback。
- 可能产生副作用的 Tool。

相同 key、相同 operation、相同规范化请求哈希返回第一次结果；相同 key 复用到不同内容返回 `IDEMPOTENCY_KEY_REUSED`。

## 10. 核心错误码

```text
AUTHENTICATION_REQUIRED
SERVICE_IDENTITY_INVALID
DELEGATION_TOKEN_INVALID
TOOL_SCOPE_DENIED
CROSS_USER_ACCESS_DENIED
VALIDATION_ERROR
VERSION_CONFLICT
IDEMPOTENCY_KEY_REQUIRED
IDEMPOTENCY_KEY_REUSED
TASK_NOT_FOUND
RUN_NOT_FOUND
RUN_NOT_RECOVERABLE
TASK_ALREADY_TERMINAL
BUDGET_EXHAUSTED
USER_INPUT_REQUIRED
CONFIRMATION_REQUIRED
PLAN_CANDIDATE_INVALIDATED
FACT_VERSION_MISMATCH
FILE_NOT_FOUND
FILE_NOT_AVAILABLE
FILE_QUARANTINED
FILE_DELETION_PENDING
TOOL_NOT_FOUND
TOOL_ARGUMENTS_INVALID
TOOL_EXECUTION_FAILED
TOOL_OUTCOME_UNKNOWN
COMPENSATION_FAILED
EVENT_SEQUENCE_GAP
INTERNAL_ERROR
```

## 11. 隐私响应

客户端和管理端响应默认不返回：

- system/developer prompt。
- 隐藏推理。
- 完整 Tool 参数和原始响应。
- Secret、Token 或签名内部材料。
- 其他用户 ID 和内容。
- 后端堆栈和基础设施拓扑细节。
