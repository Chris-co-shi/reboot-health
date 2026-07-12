# 架构

Health Platform 是独立部署的 Python 3.12 模块化单体：FastAPI 主服务、同步 SQLAlchemy/psycopg、单一 PostgreSQL、Redis 可丢弃缓存，以及每 Pod 一个 lifespan 管理后台线程。Composition Root 显式组装 Settings、Engine、SessionFactory、UoW、Repository、缓存、加密、邮件、OAuth、后台 Worker、Router 和 OTel。

依赖方向为 interfaces/adapters → application → domain；Domain 不依赖框架。事务内禁止外部 I/O，可靠副作用由同事务 Outbox 在提交后处理。该内部单体不改变 Health Platform 与 health-agent 的独立服务边界。
