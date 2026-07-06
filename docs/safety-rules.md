# 安全规则

## 1. 原则

- 安全约束必须由确定性程序规则执行。
- AI 提示词只能作为补充，不能作为唯一安全措施。
- 医疗相关输出只做提醒，不做诊断。
- 保守降级优先于自动升级。
- 被规则阻断的调整不能被应用。

## 2. 规则输出模型

```json
{
  "ruleCode": "SLEEP_LOW_BLOCK_VOLUME_INCREASE",
  "decision": "BLOCK",
  "severity": "HIGH",
  "message": "连续睡眠不足时禁止升级训练量。",
  "evidence": {},
  "blockedAdjustmentTypes": [
    "INCREASE_VOLUME",
    "INCREASE_INTENSITY"
  ]
}
```

决策值：

- `ALLOW`：允许。
- `WARN`：允许但必须提示。
- `BLOCK`：阻断。

## 3. MVP 必做规则

以下规则在 M4 开始实现。M2A-FIX 只实现健康约束和目标管理中的状态安全规则。

### AI 不得删除健康约束

触发：

- AI 建议删除、停用或弱化健康约束。

结果：

- `BLOCK`。

### AI 不得直接发布计划

触发：

- AI 输出试图把计划状态设为 `ACTIVE`。

结果：

- `BLOCK`。

### 疼痛阻断训练升级

触发：

- 某部位疼痛评分达到阈值。
- AI 建议增加该相关部位训练量、强度或复杂度。

结果：

- `BLOCK` 或 `WARN`，具体取决于阈值。

### 睡眠不足阻断训练升级

触发：

- 连续睡眠不足。
- AI 建议增加训练量或强度。

结果：

- `BLOCK`。

### 游泳呛水或换气困难恶化阻断升级

触发：

- 呛水次数增加。
- 换气困难评分上升。
- AI 建议增加游泳距离、强度或复杂度。

结果：

- `BLOCK`。

### 完成率过低优先降复杂度

触发：

- 计划完成率低于阈值。
- AI 建议增加训练内容。

结果：

- `BLOCK` 增量建议。
- 推荐方向为降低复杂度或减少任务数量。

### 血压异常只提醒

触发：

- 血压记录达到异常提醒条件。

结果：

- `WARN`。
- 提示复测、记录和咨询专业人士。
- 禁止输出诊断结论。

## 4. 状态转换规则

- 所有计划调整必须创建新版本。
- 生效计划不可原地修改。
- 历史执行记录不可被计划版本变化影响。
- 调整建议应用前必须有用户确认记录。
- 审计记录必须追加写。

## 5. M2.5-A 设备与 Agent 安全边界

- 首台设备初始化只能由服务端 CLI 生成的一次性 bootstrap code 启动。
- 普通 HTTP 接口不得生成 bootstrap code。
- bootstrap code、access token、refresh credential 均不得明文入库、入日志或入审计。
- 二维码和配对 payload 不得携带长期访问令牌，配对 payload 不得落库。
- bootstrap 消费、配对消费和 token refresh 的幂等重放必须通过加密响应信封恢复第一次签发的凭据，不得把明文凭据写入普通幂等表。
- 除 bootstrap 状态、bootstrap 消费、配对消费、token refresh 和健康检查外，所有 `/api/v1/**` 默认要求设备 access token。
- 每台设备必须有独立 `deviceId` 和独立凭据，撤销某台设备不得影响其他设备。
- 不得撤销最后一台活跃可信设备；主设备必须先显式转移后才能撤销。
- 后续设备配对必须由已授权设备发起。
- Java 是 AgentRun、设备确认、安全和业务状态的唯一权威；创建 AgentRun 后由 Java 异步调用 Python Runtime。
- Python Agent Runtime 不得连接 PostgreSQL，不得直接写业务表，不得发布计划。
- M2.5-A 只允许 `AgentRun` 进入 `READY_FOR_USER_REVIEW`，不得出现 `APPLIED`。

## 6. OPEN 未确认事项

- OPEN: 疼痛评分具体阻断阈值。
- OPEN: 连续睡眠不足的天数和分钟数阈值。
- OPEN: 游泳呛水次数增加的判定窗口。
- OPEN: 训练完成率过低的阈值。
- OPEN: 血压提醒阈值是否完全采用内置保守默认值，还是按专业建议配置。
- OPEN: 规则严重度分级是否需要用户自定义。
