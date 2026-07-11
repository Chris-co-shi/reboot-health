# 0017 六 VM Kubernetes 与架构冻结治理

## 状态

已确认，2026-07-12 生效。

替代 0004 的旧 Windows Docker/PostgreSQL 部署方向。

## 背景

第一阶段正式环境是一台 7800X3D、32GB RAM、300GB SSD 的 Hyper-V 宿主机。产品需要 K8s 灰度、滚动升级、有状态组件故障演练和完整可观测性，同时用户接受宿主机和物理 SSD 单点以及暂时没有外部备份的风险。

## 决策

- 使用 6 台 VM：3 Control Plane + 3 Worker。
- Control Plane 不承载业务 Pod。
- Health Platform、health-agent、PostgreSQL、Redis、MinIO、OTel、Prometheus、Grafana、Loki 和 Alertmanager 全部运行在 Kubernetes 内。
- 建议总分配 24GB VM 内存和约 225GB 虚拟磁盘，保留宿主机 8GB 内存和至少 75GB SSD 空间。
- 关键副本分散到 3 个 Worker，但明确不宣称跨物理故障域高可用。
- 应用支持灰度和滚动升级；Worker 使用停止领取、完成安全步骤、Checkpoint、释放 lease 和 fencing 的排空流程。
- 数据库迁移采用 Expand–Migrate–Contract。
- 当前无外部备份仍允许上线，但必须有本机备份、真实恢复演练和持续高风险告警。
- 2026-07-12 架构文档标记 FROZEN。任何架构变化必须先 ADR、同步权威文档、人工批准，再修改代码。

## 影响

正面：

- 能在有限硬件上演练 Pod、VM、数据库和发布故障。
- 实施边界和提示词不再随临时想法变化。

成本与风险：

- 单宿主机、单 SSD、单电源仍是灾难性单点。
- 32GB 内存要求严格 requests/limits、日志保留和容量管理。
- Kubernetes 发行版、CNI、Ingress、证书、PostgreSQL Operator 和 Redis 拓扑仍需技术 Spike，但不得改变冻结拓扑边界。

## 约束

- Hyper-V Checkpoint 不能代替备份。
- 五类生产验收全部通过前不得标记生产可用。
- 没有 READY Slice 和 implementation 规范时禁止代码实现。
- ChatGPT/Codex/IDE Agent 提示词不得重新定义架构；完成结果必须写回 PHASE_STATUS。
