# 运维设计

生产配置来自环境变量、ConfigMap 和 Secret；缺关键配置启动失败。数据库迁移作为单独 Job 执行，应用启动不自动改 Schema。Kubernetes Secret 只读挂载，要求 etcd Secret 静态加密，密钥备份必须与数据库备份配套。

发布采用 expand–migrate–contract。后台线程排空、Outbox 积压、失败邮件、Redis 降级、迁移版本和密钥版本均需指标/告警。本 Slice 不创建可运行 Kubernetes Manifest 或 Helm Chart。
