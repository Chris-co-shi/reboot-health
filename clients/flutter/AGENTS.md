# Flutter 客户端规则

开始任务前读取根 `AGENTS.md`、冻结权威文档、相关 ADR、当前 implementation 规范和本 README。

- Flutter 是 Android/iOS 正式用户客户端，业务能力与微信小程序对齐。
- 只调用 Health Platform，不直接调用 `health-agent`、数据库、Redis 或对象存储。
- 文件上传必须经过 Health Platform 授权流程。
- 不在客户端复制服务端状态机、权限、风险判断或用户确认权威。
- 普通用户界面不突出内部 UUID、revision、PlanVersion 或内部枚举码。
- 当前只保留可构建空壳；没有批准的客户端 Slice 时不得实现正式 API 或健康业务页面。
- 没有执行真实构建时必须标记未验证。

验证：

```bash
flutter pub get
flutter analyze
flutter test
```
