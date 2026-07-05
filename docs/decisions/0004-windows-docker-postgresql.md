# 0004 Docker 与外部 PostgreSQL 17

## 状态

已确认

## 决策

应用部署在用户私有 PC 上。后端和前端使用 Docker 容器运行，数据库使用宿主机 PostgreSQL 17。

## 原因

用户已具备本机 PostgreSQL 17 环境。应用容器化可以保持运行方式稳定，同时避免重复管理数据库容器。

## 影响

- Compose 不启动 PostgreSQL。
- 后端通过宿主机映射地址连接 PostgreSQL。
- 默认端口绑定 `127.0.0.1`。
- Tailscale 负责远程访问边界。
- 真实数据库密码只通过本地环境变量或未提交的 `.env` 提供。

## OPEN

- OPEN: Tailscale Serve 或绑定 Tailscale IP 的最终方式。
- OPEN: 备份目录和保留策略。
