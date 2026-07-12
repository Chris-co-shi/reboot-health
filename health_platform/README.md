# Python Health Platform

`health_platform/` 是 reboot-health 的业务平台、数据权威和控制面。它管理用户身份与业务权限，以及 Conversation、Fact、Plan、Risk、File、Secret 和业务审计。

微信小程序、Flutter 和 Vue Admin 只能访问 Health Platform。Health Platform 通过内部 HTTPS、mTLS 和短期 JWT 调用 `health-agent`；`health-agent` 不得直接连接 Platform 数据库。

当前目录只是 Phase 3B 的框架无关 Python 服务骨架。尚未实现业务对象、Web 框架、数据库、Redis、对象存储、REST Endpoint 或生产部署能力。

## 包边界

```text
src/health_platform/
├── domain/       业务领域边界
├── application/  应用用例边界
├── ports/        外部能力端口
├── adapters/     基础设施适配器
└── interfaces/   服务接口边界
```

这些目录只表达依赖方向，不预先固化业务 Schema。后续实现必须先有对应的 `READY` Slice。

## 验证

```bash
python3 -m compileall src tests
python3 -m unittest discover -s tests -v
```
