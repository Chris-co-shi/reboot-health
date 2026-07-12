# 状态机（FROZEN）

## 1. 总则

- 所有状态转换由确定性代码执行。
- 模型只能提出意图或候选，不能直接设置终态。
- 每次转换必须校验当前状态、revision、操作者、权限、前置条件和幂等键。
- 非法转换返回结构化错误，不做隐式修复。
- 终态对象不得通过普通更新接口重新激活。

## 2. AgentTask 状态机

```text
CREATED
→ QUEUED
→ ACTIVE
   ├→ WAITING_USER_INPUT
   ├→ WAITING_CONFIRMATION
   ├→ COMPLETED
   ├→ FAILED
   ├→ TERMINATED
   ├→ BUDGET_EXHAUSTED
   └→ MANUAL_INTERVENTION_REQUIRED
```

语义：

| 状态 | 含义 |
|---|---|
| `CREATED` | 已持久化但尚未加入调度 |
| `QUEUED` | 已等待 Worker 领取 |
| `ACTIVE` | 至少一个 Run 正在执行 |
| `WAITING_USER_INPUT` | Run 等待关键事实或用户补充 |
| `WAITING_CONFIRMATION` | 等待 Plan、风险、纠错、追加预算或副作用确认 |
| `COMPLETED` | Task 目标已完成或形成最终用户结果 |
| `FAILED` | 当前 Task 无法可靠完成，且无自动恢复路径 |
| `TERMINATED` | 用户或管理员终止 |
| `BUDGET_EXHAUSTED` | 达到硬预算，等待用户是否追加 |
| `MANUAL_INTERVENTION_REQUIRED` | 状态、副作用或恢复结果无法自动确认 |

Task 可以包含多个 Run。Run 正式失败或预算耗尽后，新的执行使用新 Run，不复活旧 Run。

## 3. AgentRun 状态机

```text
CREATED
→ QUEUED
→ RUNNING
   ├→ WAITING_USER_INPUT → RUNNING
   ├→ WAITING_CONFIRMATION → RUNNING
   ├→ COMPLETED
   ├→ FAILED_RETRYABLE
   ├→ FAILED_PERMANENT
   ├→ TERMINATION_REQUESTED → TERMINATED
   ├→ BUDGET_EXHAUSTED
   └→ MANUAL_INTERVENTION_REQUIRED
```

规则：

- `WAITING_USER_INPUT` 和 `WAITING_CONFIRMATION` 仍属于同一 Run。
- transient 模型/Tool 错误在 Step 内有限重试，不立即创建新 Run。
- `FAILED_RETRYABLE` 终态后，如用户或策略重试，创建引用旧 Run 的新 Run。
- `FAILED_PERMANENT` 只有在输入、能力或安全边界改变后才允许新 Run。
- `TERMINATION_REQUESTED` 表示协作式终止；当前不可中断步骤完成后停止。
- 终止时丢弃未完成模型输出；已确认读取结果可以保留。

## 4. AgentStep 状态机

```text
PENDING
→ RUNNING
   ├→ SUCCEEDED
   ├→ RETRY_WAIT → RUNNING
   ├→ FAILED
   ├→ CANCEL_REQUESTED → CANCELLED
   └→ UNKNOWN_OUTCOME
```

`UNKNOWN_OUTCOME` 用于模型、Tool 或外部副作用在崩溃时结果不确定，禁止直接重放。

## 5. Checkpoint 与恢复分类

Checkpoint 分类：

| 分类 | 自动恢复 |
|---|---:|
| `DRIVE_READY` | 是 |
| `MODEL_CALL_IN_FLIGHT` | 否，除非 Provider 提供可证明的幂等响应恢复 |
| `TOOL_CALL_IN_FLIGHT` | 仅明确幂等且结果可查询时 |
| `FINALIZING` | 否，先对账终态 |

恢复规则：

1. 新 Worker 必须获得更高 fence generation。
2. 旧 owner 即使恢复也不能继续写。
3. 可重用只读结果必须重新校验来源版本、TTL、scope 和用户归属。
4. 结果不确定或补偿失败时进入 `MANUAL_INTERVENTION_REQUIRED`。

## 6. 消息消费状态

每条用户消息维护：

```text
RECEIVED → PERSISTED → AVAILABLE → CONSUMED
                         └→ SUPERSEDED（仅在明确被新消息整体取代时）
```

- Run 执行中收到多条消息时，当前不可中断 Step 先完成。
- 之后按 `messageSequence` 处理所有未消费消息。
- 新消息与旧 Fact 冲突时，先生成纠错候选，不静默覆盖。

## 7. PlanVersion 状态机

```text
CANDIDATE
├→ CONFIRMED
├→ REJECTED
└→ ABANDONED

CONFIRMED
└→ SUPERSEDED
```

规则：

- `CANDIDATE` 可以被用户局部编辑，但每次编辑增加 revision。
- 确认要求 expectedRevision、Fact 版本和风险确认均匹配。
- 新确认版本产生后，旧 `CONFIRMED` 进入 `SUPERSEDED`。
- Task 终止、关键 Fact 修正或候选依据失效时进入 `ABANDONED`，不得再次确认。
- 旧候选默认不在用户主界面展示，但保留历史和失效原因。

## 8. PlanRevision 状态机

```text
PROPOSED
├→ APPLIED
├→ REJECTED
├→ EXPIRED
└→ CONFLICTED
```

- 用户直接发起且通过确定性安全检查的低风险修改可从 `PROPOSED` 立即进入 `APPLIED`。
- Agent 发起的修改必须等待用户确认。
- revision 不匹配进入 `CONFLICTED`，客户端刷新后重新提交。
- 只允许修改未完成部分；已完成 ExecutionRecord 不受影响。

## 9. FactCandidate 状态机

```text
PENDING_CONFIRMATION
├→ CONFIRMED
├→ MODIFIED_AND_CONFIRMED
├→ REJECTED
├→ INVALIDATED
└→ SUPERSEDED
```

文件提取的候选必须逐项转换。批量“全部自动确认”不允许成为默认行为。

## 10. HealthFact 状态机

```text
ACTIVE
├→ SUPERSEDED
├→ RETRACTED
└→ DELETED_BY_POLICY（仅允许法律/隐私删除流程）
```

- 历史纠正通过新 Fact + FactRevision 实现，旧 Fact 进入 `SUPERSEDED`。
- `RETRACTED` 表示用户确认该事实不应继续生效，但记录仍为审计历史。
- 业务普通删除不得物理清除历史审计。

## 11. RiskFinding 状态机

```text
OPEN
├→ ACKNOWLEDGED
├→ ACCEPTED_WITH_OVERRIDE
├→ MITIGATED
├→ DISMISSED
└→ SUPERSEDED
```

- `ACKNOWLEDGED`：用户已阅读但尚未决定。
- `ACCEPTED_WITH_OVERRIDE`：用户在二次确认后仍选择原方案。
- `MITIGATED`：采用更安全替代方案。
- `DISMISSED`：证据不足或不适用，必须记录理由。

## 12. PendingAction 状态机

```text
PENDING
├→ APPROVED
├→ REJECTED
├→ EXPIRED
├→ CANCELLED
└→ ORPHANED
```

- action 绑定 Task、Run、用户、内容哈希、revision 和过期时间。
- 批准只能消费一次。
- orphan 扫描默认 dry-run；只清理过期且未引用的 PendingAction。

## 13. ToolCall 状态机

```text
CREATED
→ VALIDATED
→ RUNNING
   ├→ SUCCEEDED
   ├→ FAILED_RETRYABLE
   ├→ FAILED_PERMANENT
   ├→ UNKNOWN_OUTCOME
   └→ COMPENSATION_REQUIRED
```

补偿：

```text
COMPENSATION_REQUIRED
→ COMPENSATING
   ├→ COMPENSATED
   └→ COMPENSATION_FAILED → MANUAL_INTERVENTION_REQUIRED
```

补偿只能调用 ToolDefinition 显式声明的确定性补偿 Tool，不能由模型临时编造。

## 14. FileAsset 状态机

```text
UPLOAD_REQUESTED
→ UPLOADING
→ UPLOADED
→ VERIFYING
   ├→ AVAILABLE
   ├→ QUARANTINED
   └→ REJECTED

AVAILABLE
├→ PROCESSING → AVAILABLE
├→ DELETION_PENDING
└→ EXPIRED（仅临时文件）

DELETION_PENDING
├→ DELETED
└→ DELETION_FAILED
```

规则：

- `VERIFYING` 校验大小、Hash、MIME、扩展名和恶意内容。
- `QUARANTINED` 文件不得提供给 Agent。
- 删除申请后立即禁止新下载、解析和 RAG 召回。
- `DELETED` 前必须清理原件、派生物、Chunk、向量、缓存和 Sandbox 临时副本。
- 删除失败持续告警并重试，不能恢复为普通 AVAILABLE。

## 15. FileExtractionCandidate 状态机

与 FactCandidate 相同，但额外绑定：

- `fileId` 和对象版本。
- 页码/区域/原文引用。
- 提取器与模型版本。

文件删除、版本变化或重新上传会使未确认候选进入 `INVALIDATED`。

## 16. Outbox/Inbox 状态机

### Outbox

```text
PENDING → PUBLISHING
           ├→ PUBLISHED
           ├→ RETRY_WAIT
           └→ DEAD_LETTER
```

`DEAD_LETTER` 不删除事件；管理员修复后可重放。

### Inbox

```text
RECEIVED
├→ APPLIED
├→ DUPLICATE_IGNORED
├→ GAP_DETECTED
└→ FAILED
```

`GAP_DETECTED` 触发事件拉取或 Snapshot 对账。

## 17. Provider fallback

一次模型尝试：

```text
STARTED
├→ SUCCEEDED
├→ RETRYABLE_FAILURE → RETRIED
├→ FALLBACK_REQUIRED → BACKUP_PROVIDER
└→ PERMANENT_FAILURE
```

切换 Provider 前丢弃未完成输出，从安全 Checkpoint 重新执行；不得把两个 Provider 的半成品拼接成正式结果。

## 18. 管理操作

管理员只能对异常 Run 执行：

- `RETRY`：创建新 Run。
- `RECOVER`：从可验证 Checkpoint 恢复。
- `TERMINATE`：请求协作式终止。
- `REPLAY_EVENT`：重发 Outbox 或拉取对账。

管理员不能直接修改终态、Fact、Plan、RiskAcknowledgement 或用户确认记录。

## 19. Identity 状态机

```text
User: PENDING_VERIFICATION → ACTIVE → DISABLED / DELETION_PENDING → DELETED
Session: ACTIVE → REVOKED / EXPIRED
TokenFamily: ACTIVE → REVOKED / REPLAY_COMPROMISED
EmailVerification: PENDING → CONSUMED / SUPERSEDED / EXPIRED
PasswordRecovery: PENDING_EMAIL → EMAIL_VERIFIED → READY → CONSUMED / EXPIRED
MFA: DISABLED → PENDING_CONFIRMATION → ENABLED → DISABLED
DeletionRequest: COOLING_OFF → CANCELLED / READY → PROCESSING → COMPLETED / FAILED
Outbox: PENDING → PROCESSING → PUBLISHED / FAILED → PENDING
```

Refresh Token 轮换必须原子消费旧 Token 并创建新 Token；检测已消费 Token 时不得继续刷新，必须撤销 Family并审计。账号禁用、密码变更和删除申请必须按合同撤销 Session/Token。
