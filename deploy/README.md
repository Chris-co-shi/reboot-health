# Kubernetes 部署目标目录

正式目标为 6 台 VM 的 Kubernetes 集群：3 台 Control Plane 和 3 台 Worker，全部应用及有状态组件运行在 Kubernetes 内。

目标组件：

- PostgreSQL
- Redis Streams
- MinIO
- Health Platform
- `health-agent-api`
- `health-agent-worker`
- OpenTelemetry Collector
- Prometheus
- Grafana
- Loki
- Alertmanager

当前目录只是 Phase 3B 结构占位，不包含可运行 Manifest、Helm Chart 或生产配置。Kubernetes 发行版、CNI、Ingress、证书管理、PostgreSQL Operator 和 Redis 拓扑仍需技术 Spike/ADR，不能把占位目录描述为已部署。

Docker Compose 不再是生产架构。后续本地开发方案需要单独批准，不得恢复旧生产 Compose 链路。
