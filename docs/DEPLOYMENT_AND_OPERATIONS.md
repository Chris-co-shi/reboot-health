# 部署与运维（FROZEN）

## 1. 第一阶段正式环境

宿主机：

```text
AMD Ryzen 7 7800X3D（8C/16T）
32GB RAM
Hyper-V
300GB SSD 专供 VM
```

正式拓扑为 6 台 VM：

| VM | 角色 | vCPU | 内存 | 建议虚拟磁盘 |
|---|---|---:|---:|---:|
| VM1 | Kubernetes Control Plane 1 | 2 | 2GB | 15GB |
| VM2 | Kubernetes Control Plane 2 | 2 | 2GB | 15GB |
| VM3 | Kubernetes Control Plane 3 | 2 | 2GB | 15GB |
| VM4 | Kubernetes Worker 1 | 4 | 6GB | 60GB |
| VM5 | Kubernetes Worker 2 | 4 | 6GB | 60GB |
| VM6 | Kubernetes Worker 3 | 4 | 6GB | 60GB |

总计分配 24GB 内存和约 225GB 虚拟磁盘，宿主机保留约 8GB 内存和至少 75GB SSD 余量。

VM 默认使用固定内存。不得把 32GB 全部分配给 VM，也不得以动态 VHDX 的标称容量掩盖物理 SSD 超卖。

## 2. 高可用边界

本环境可以演练和承受：

- 单个 Pod 故障。
- 单个 Worker VM 故障。
- 单个应用实例故障。
- PostgreSQL/Redis 单实例故障。
- 滚动升级和灰度期间的实例替换。

本环境**不能**承受：

- Hyper-V 宿主机故障。
- Windows 或 Hyper-V 整体故障。
- 单块物理 SSD 损坏。
- 主机电源、主板或网络整体故障。

因此只能声明 **Pod/VM/实例级高可用，接受宿主机和物理存储单点**，不得描述为跨故障域生产高可用。

## 3. Kubernetes 角色

- 3 个 Control Plane 只运行 Kubernetes 核心组件，不调度业务 Pod。
- 3 个 Worker 运行所有应用和有状态组件。
- 关键有状态副本使用 `podAntiAffinity` / topology spread 分散到不同 Worker。
- PodDisruptionBudget 防止维护时同时驱逐过多副本。
- 所有应用设置 requests/limits、readiness、liveness 和 startup probes。

Kubernetes 发行版、CNI、Ingress、证书管理和具体 Operator 在实施前通过技术 Spike 和 ADR 选择；选择不得改变六 VM、三 Worker 和全部组件在 K8s 内运行的冻结边界。

## 4. Kubernetes 内组件

```text
Application
├── Health Platform API / Worker
├── health-agent-api
├── health-agent-worker
├── Vue Admin 静态站点/服务
└── Ingress / internal gateway

Data and coordination
├── PostgreSQL HA cluster
├── Redis + Sentinel/Cluster（按实施 ADR）
├── MinIO
└── pgvector

Observability
├── OpenTelemetry Collector
├── Prometheus
├── Grafana
├── Loki
└── Alertmanager
```

所有有状态组件都运行在 Kubernetes 内。Kubernetes 只负责调度和生命周期，不代替 PostgreSQL、Redis、MinIO 自己的复制、一致性和恢复机制。

## 5. 存储

### 原则

- PostgreSQL、Redis、MinIO、Prometheus 和 Loki 使用独立 PVC。
- 不把数据库、对象存储和日志写入同一 PVC。
- 使用具有容量上限的 StorageClass/PV。
- 不以 Hyper-V Checkpoint 代替数据库或对象存储备份。
- 宿主 SSD 低于 20% 空闲进入警告，低于 10% 进入高危告警并限制非必要写入。

由于三 Worker 的 VHDX 仍位于同一物理 SSD，副本只提供逻辑隔离和 VM 故障恢复，不提供物理介质冗余。

## 6. PostgreSQL

要求：

- 至少 3 个数据库实例或满足多数派/自动切换要求的等价拓扑。
- 明确 primary/replica、自动故障转移和防脑裂机制。
- Platform 和 health-agent 使用独立数据库/Schema 和最小权限账号。
- pgvector 与业务表遵循同一备份、恢复和版本策略。
- WAL、连接数、shared buffers 和 work memory 按 6GB Worker 限制保守配置。
- 故障转移、旧 primary 恢复和数据一致性必须通过演练。

具体 PostgreSQL Operator/Patroni 组合需要技术 Spike；不得在未验证持久卷和故障转移的情况下标记生产完成。

## 7. Redis

Redis 用于 Streams、协调、lease 和短期缓存，不作为业务权威。

要求：

- 至少分散到 3 个 Worker 的故障检测/仲裁能力。
- 明确持久化策略、最大内存和 eviction policy。
- Redis 数据丢失时 PostgreSQL reconciler 能重建待执行调度。
- consumer group、pending entries、延迟重试和 dead-letter 有监控。
- Redis 故障不得导致旧 Worker 绕过 fence 继续写。

## 8. MinIO 和文件容量

- 通过 `ObjectStorageProvider` 使用 MinIO。
- MinIO 管理端不对公网开放。
- 对象、派生物和临时文件按 userId、业务用途和版本组织。
- 用户配额、单文件限制、桶生命周期和删除对账必须配置。
- 300GB 环境优先保证 PostgreSQL、文件原件和恢复空间，禁止无限保留派生物。

容量告警至少覆盖：

- MinIO 可用空间。
- 未完成 multipart upload。
- 删除失败对象。
- 派生物增长率。
- 文件与数据库元数据不一致。

## 9. 日志与指标保留

第一阶段默认基线：

```text
Loki 原始日志：7 天
Prometheus 指标：15 天
health-agent 敏感执行上下文：短期可配置
普通 Task/Run 元数据：较长可配置
业务审计：长期
```

这些是部署默认值，不是法律保留结论；具体天数必须可配置、可审计并结合实际容量调整。

Docker/container runtime 日志必须启用大小和文件数量轮转。

## 10. 灰度发布

Health Platform 和 health-agent-api：

- 多副本 Deployment。
- readiness 通过后才接流量。
- 支持滚动升级和金丝雀流量。
- 灰度期间同时兼容当前和前一合同版本。

health-agent-worker：

```text
旧 Worker 停止领取新任务
→ 继续完成当前安全步骤
→ 可完成的 Run 正常结束
→ 需要移交的 Run 持久化 Checkpoint 并释放 lease
→ 新 Worker 获取更高 fence generation
→ 旧 Worker 退出
```

禁止直接杀死 Worker 后假设所有 in-flight 模型和 Tool 可安全重放。

## 11. 数据库迁移

采用 Expand–Migrate–Contract：

1. **Expand**：新增兼容字段、表或索引，不删除旧结构。
2. **Migrate**：新旧应用同时兼容，后台迁移和对账。
3. **Contract**：确认所有旧实例退出、数据迁移完成、回滚窗口关闭后再删除旧结构。

原则：

- 应用可以回滚到兼容版本。
- 已执行的数据迁移不得依赖危险的简单 down 脚本强行回退。
- 破坏性迁移前必须有备份、恢复演练、影响评估和人工批准。
- migration job 必须单实例、可观察、可重入或明确 fail-closed。

## 12. 备份和恢复

当前没有 NAS、第二物理设备或云对象存储，用户明确接受先上线并承担外部灾备缺失风险。

上线前仍必须具备：

- PostgreSQL 本机备份。
- MinIO 关键对象清单和备份策略。
- 配置、Secret metadata 和 Kubernetes manifest 的版本化备份。
- 完整恢复演练。
- 管理端持续显示“无外部备份/宿主机单点”高风险。

要求：

- 备份文件与在线数据库/PVC 逻辑分离。
- 备份完整性使用 checksum 验证。
- 恢复演练必须实际创建新实例并验证业务读取，不接受只检查备份文件存在。
- 外部备份接入 NAS 或云对象存储后，通过新 ADR 更新 RPO/RTO。

当前不得承诺接近零数据丢失或宿主机灾难恢复。

## 13. 对账和自愈

周期 Reconciler 至少检查：

- PostgreSQL 中 QUEUED/RUNNING Task 与 Redis Streams 是否一致。
- lease 超时和 fencing。
- Outbox 未发布、dead-letter 和回调缺口。
- Platform Task 投影与 health-agent Snapshot。
- MinIO 对象与 FileAsset 元数据。
- RAG Chunk 的 source/version/validStatus。
- 删除请求是否清理全部派生数据。

Reconciler 只能执行有确定规则的修复；结果不确定进入人工处理。

## 14. 可观测性

统一关联：

```text
traceId
taskId
runId
stepId
toolCallId
maskedUserId
```

指标至少包含：

- Task 成功/失败/等待/终止率。
- queue latency、execution latency。
- model calls、token、fallback、成本。
- Tool 错误、重试、未知结果和补偿。
- lease、stale recovery、fence 拒绝。
- Outbox/Inbox backlog、sequence gap、reconciliation。
- PostgreSQL/Redis/MinIO 容量和健康。
- Sandbox 创建、超时、资源和网络拒绝。

## 15. 告警

| 级别 | 渠道 |
|---|---|
| 低/信息 | 管理 Web |
| 中 | 管理 Web 持久待办 |
| 高/严重 | 管理 Web + 管理员邮件 |

高危场景：

- 未知副作用或补偿失败。
- Secret 访问、解密、签发或轮换异常。
- 跨用户访问或潜在数据泄露。
- Task 无法恢复。
- 持续 Outbox/Inbox/对账失败。
- PostgreSQL 故障转移失败。
- SSD/MinIO/PostgreSQL 空间危险。
- 成本或模型调用异常激增。
- 服务身份认证连续失败。

告警必须支持去重、升级、确认和恢复通知。

## 16. 运维操作边界

允许：

- Pod/Deployment 滚动重启。
- Run 重试、恢复和终止。
- Outbox 重放和 Snapshot 对账。
- 数据库故障转移和副本重建。
- 备份、恢复和容量扩展。

禁止：

- 直接修改数据库状态伪造 Task 成功。
- 删除审计掩盖故障。
- 跳过 migration/版本检查。
- 用 Redis 手工写值替代 PostgreSQL 权威。
- 在未记录原因时强制删除 PVC 或对象。

## 17. 第一阶段生产门槛

必须形成可审计证据：

- K8s 安装和节点清单。
- 应用灰度和回滚记录。
- PostgreSQL、Redis、MinIO 故障演练。
- Worker 中断和 Checkpoint 恢复。
- Outbox 回调丢失、重复和乱序演练。
- 备份恢复演练。
- 安全、跨用户和 Secret 测试。
- 容量、告警和日志脱敏验证。

缺少任一类时，Phase 只能标记 `IMPLEMENTED_WITH_BLOCKERS`，不能标记生产完成。
