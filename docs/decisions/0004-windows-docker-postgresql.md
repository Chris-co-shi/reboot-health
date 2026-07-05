# 0004 Windows 10 Docker 与外部 PostgreSQL 17

## 状态

已确认

## 决策

应用部署在用户 Windows 10 台式机上。后端和前端使用 Docker 容器运行，数据库使用宿主机已有 PostgreSQL 17。

## 原因

用户已具备本机 PostgreSQL 17 环境。应用容器化可以保持运行方式稳定，同时避免重复管理数据库容器。

## 影响

- Compose 不启动 PostgreSQL。
- 后端通过 `host.docker.internal` 连接宿主机数据库。
- 默认端口绑定 `127.0.0.1`。
- Tailscale 负责远程访问边界。

## OPEN

- OPEN: 数据库名、用户名和密码。
- OPEN: Tailscale Serve 或绑定 Tailscale IP 的最终方式。
- OPEN: 备份目录和保留策略。
