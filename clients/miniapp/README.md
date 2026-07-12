# 微信小程序客户端

微信小程序是 reboot-health 面向最终用户的正式客户端，业务能力应与 Flutter Android/iOS 对齐。

边界：

- 只调用 Health Platform，不直接调用 `health-agent`。
- 不直接访问 PostgreSQL、Redis 或 MinIO。
- 文件上传必须经过 Health Platform 的身份、配额、类型与授权流程。
- 不持有 MinIO 长期凭证或绕过 Platform 获取对象。

当前目录只是 Phase 3B 的边界占位，尚未进入客户端实现 Phase，也未选择原生小程序、Taro、uni-app 或其他技术方案。
