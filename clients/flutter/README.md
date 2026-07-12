# reboot-health Flutter Client

Flutter 是 reboot-health 面向 Android/iOS 用户的正式客户端，业务能力将与微信小程序保持一致。

调用边界：

- 只调用 Health Platform。
- 不直接调用 `health-agent`。
- 不直接访问 PostgreSQL、Redis、MinIO 或其他对象存储。
- 文件上传必须经过 Health Platform 的授权流程。

当前为 Phase 3B 的最小可构建客户端空壳，保留 Flutter 工程和通用主题基础。尚未接入正式 Health Platform API，也未实现健康业务页面、认证或文件上传。

## 验证

```bash
flutter pub get
flutter analyze
flutter test
```
