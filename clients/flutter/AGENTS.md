# Flutter 规则

- Flutter 是正式用户客户端。
- 客户端只调用 Java API，不直接调用 Python。
- 后端是业务状态和安全判断的最终权威。
- API 模型、页面模型和本地状态分离。
- 普通页面不展示 UUID、revision、PlanVersion 或内部枚举码。
- 移动端优先，桌面端使用适配布局。
- 自然语言用于表达，卡片用于行动和确认。
- 不复刻 Vue 管理后台。
- 平台差异通过适配器封装。
- M2.5-A 只验证应用骨架、设备管理和 AgentRun 卡片。
- 未经明确任务，不实现访谈、Program、Phase、WeeklyPlan、DailyAction 或 Observation。
- 没有执行真实构建时必须标记为未验证。

验证：

```bash
flutter pub get
flutter analyze
flutter test
```
