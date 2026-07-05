# AI 调整设计

## 1. 设计原则

- AI 只生成建议，不直接修改生效计划。
- AI 输出必须是结构化 JSON。
- JSON 必须通过 Schema 校验。
- 确定性安全规则先于 AI 应用。
- 用户确认后，领域服务才创建新的计划版本。

## 2. AI 使用场景

MVP 使用 AI 做两件事：

1. 起草第一周计划。
2. 基于周分析生成调整建议。

不使用 AI 做：

- 医学诊断。
- 自动发布计划。
- 自动删除健康约束。
- 自动忽略疼痛、血压、睡眠、呛水等安全信号。

## 3. 输入上下文

AI 输入应由后端组装，包含：

- 用户档案摘要。
- 目标。
- 健康约束。
- 当前计划版本。
- 7 天执行记录。
- 身体指标趋势。
- 症状和主观状态记录。
- 周分析结果。
- 确定性规则输出。

约束：

- 不把无关日志、内部异常栈、密钥放入 AI 上下文。
- 对健康约束使用明确、不可删除的系统级上下文。

## 4. 输出对象

AI 只能输出 `AdjustmentProposal` 或计划草案结构。

调整建议结构草案：

```json
{
  "schemaVersion": "1.0",
  "period": {
    "start": "2026-07-01",
    "end": "2026-07-07"
  },
  "summary": "本周完成率偏低，建议降低复杂度。",
  "overallRiskLevel": "LOW",
  "items": [
    {
      "domain": "TRAINING",
      "changeType": "REDUCE_COMPLEXITY",
      "targetRef": {
        "type": "PLAN_ITEM",
        "id": "plan-item-id"
      },
      "before": {},
      "after": {},
      "rationale": "完成率不足，先降低复杂度。",
      "evidenceRefs": [],
      "risks": [],
      "safetyRuleRefs": []
    }
  ]
}
```

## 5. 调整工作流

```text
WeeklyAnalysis
  -> SafetyRule pre-check
  -> AI request
  -> JSON Schema validation
  -> semantic validation
  -> SafetyRule post-check
  -> AdjustmentProposal saved
  -> user decision
  -> PlanVersion created by domain service
```

## 6. 校验层级

### Schema 校验

检查：

- 必填字段。
- 枚举值。
- 数据类型。
- 数组长度。
- JSON 结构版本。

失败处理：

- 保存失败原因。
- 不进入用户确认页。
- 不生成计划版本。

### 语义校验

检查：

- `targetRef` 是否存在。
- `before` 是否匹配当前计划版本。
- 是否引用不存在的计划项。
- 是否试图删除健康约束。

### 安全规则校验

检查：

- 疼痛阈值。
- 睡眠不足。
- 游泳呛水或换气困难恶化。
- 完成率过低。
- 血压异常提醒。

## 7. 用户确认

用户可以：

- 全部接受。
- 部分接受。
- 全部拒绝。

系统必须展示：

- 调整前。
- 调整后。
- 依据。
- 风险。
- 被规则拦截的原因。

## 8. OPEN 未确认事项

- OPEN: 实际 OpenAI 兼容接口供应商。
- OPEN: 实际模型名称。
- OPEN: AI 请求超时时间和重试策略。
- OPEN: AI 调用失败时是否允许手动创建调整建议。
- OPEN: 第一周计划草案的 JSON Schema 是否与调整建议共用一套基础结构。
