# 微信小程序规则

开始任务前读取根 `AGENTS.md`、冻结权威文档、相关 ADR、当前 implementation 规范和本 README。

- 微信小程序是正式用户客户端，业务能力与 Flutter 对齐。
- 只调用 Health Platform，不直接调用 `health-agent`、数据库、Redis 或 MinIO。
- 文件上传必须经过 Health Platform 授权流程。
- 未有批准的客户端 Slice 前不得选择技术栈、实现业务页面或固化 API Schema。
- 不得在客户端复制服务端状态机、权限或确认权威。
