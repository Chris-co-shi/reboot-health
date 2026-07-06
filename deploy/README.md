<div align="center">

# Deployment

### reboot-health 私有部署入口

<p>
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker%20Compose-Local%20Stack-2496ED?logo=docker&logoColor=white">
  <img alt="Scope" src="https://img.shields.io/badge/Scope-Private%20Deployment-6C5CE7">
</p>

</div>

## 📦 Components

当前部署栈负责协调：

- Java Health Domain Kernel。
- Python Health Agent Harness。
- 冻结的 Vue Debug Tool。
- 按环境配置使用的 PostgreSQL 17。

Flutter 是用户客户端，不由本 Compose 栈托管。

## ✅ Validate

在仓库根目录执行：

```bash
docker compose -f deploy/docker-compose.yml config
```

## ▶️ Start

```bash
docker compose -f deploy/docker-compose.yml up -d
```

## 🔎 Inspect

```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f
```

## ⏹️ Stop

```bash
docker compose -f deploy/docker-compose.yml down
```

## 🛡️ Configuration rules

- 真实凭据和私有网络地址必须通过本地环境配置提供。
- 不提交生产密钥或加密材料。
- 默认不把服务暴露到公网。
- M2.5-A 不需要 Redis、消息队列、向量数据库或工作流平台。
- 部署改动不得静默改变应用业务行为。

详细约束见 [`AGENTS.md`](AGENTS.md)和[`../docs/architecture.md`](../docs/architecture.md)。
