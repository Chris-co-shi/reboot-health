# 部署目录规则

开始任务前读取根 `AGENTS.md`、`docs/DEPLOYMENT_AND_OPERATIONS.md`、ADR 0017、当前 implementation 规范及本 README。

- 正式边界是 3 Control Plane + 3 Worker，全部组件运行在 Kubernetes 内。
- 当前 K8s 关键技术选择仍需 Spike/ADR，不得自行选择或创建虚假可运行声明。
- 不得把 Docker Compose 恢复为生产架构。
- 不在部署任务中修改业务边界、状态机或服务合同。
- 不提交 Secret、真实内部地址、签名 URL 或凭据。
- 未执行真实部署和故障演练时必须明确标记未验证。
