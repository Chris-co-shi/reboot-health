# modules 通用骨架规则

## 适用范围

本文件适用于 `health_platform.modules.*` 下所有尚未具备专属规则的模块。当前为 `SKELETON` 的模块：

```text
conversation
fact
goal
plan
risk
file
secret
agent_integration
```

`identity` 与 `audit` 已有完整实现，不受本通用规则约束；它们继续在各自模块下维护 `domain / application / adapters / ports / interfaces` 五层结构。

## 状态与边界

- 当前状态：`SKELETON`。禁止提前实现业务、数据库 Schema、API、状态机、第二套契约或调用其他模块 Repository。
- 必须先读取仓库根 `AGENTS.md`、`docs/README.md`、`docs/PHASE_STATUS.md`、对应 ADR 与对应 `READY` 的 implementation 规范，才能进入实现。
- 模块对外能力只能通过 Application Port 暴露；模块之间禁止直接互相调用 Repository。
- 跨模块可靠副作用必须经 Audit 模块的 Outbox 同步写入，禁止模块自带后台线程或网络出口。
- 跨模块同步事件仅允许进程内 Domain Event，不允许 import 其他模块的领域类型。

## 五层目录约定

模块落地时按以下五层组织；当前 SKELETON 阶段不预先创建空目录与占位 `__init__.py`。

```text
modules/<name>/
├── domain/         纯领域模型与不变量，不依赖外部框架
├── application/    用例编排与事务协调
├── ports/          对外契约与协议（邮件、缓存、SMTP 等）
├── adapters/       SQLAlchemy、Redis、SMTP、HTTP 客户端等基础设施实现
└── interfaces/     HTTP/CLI/Worker 等进程边界
```

- 只允许 `domain` 不依赖本模块之外的类型。
- `application` 只依赖本模块的 `domain` 与 `ports`。
- `adapters` 实现 `ports`，允许依赖外部 SDK；不暴露给其它模块 import。
- `interfaces` 调用 `application`，是模块唯一的进程入口。

## 公共规则

- 公共规则请阅读仓库根 `AGENTS.md` 与 `health_platform/AGENTS.md`；本文件不重复。
- 任何模块进入实现阶段，必须先新增 `modules/<name>/AGENTS.md` 取代本通用文件中的对应章节。