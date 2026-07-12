# API 设计

公开 Identity API 位于 `/api/v1`，JSON 使用 snake_case 和 RFC3339 UTC。成功直接返回资源 DTO；错误为 `error_code/message/trace_id/details`。写接口按风险支持 `Idempotency-Key`，可修改资源使用 ETag/If-Match。

端点覆盖注册、登录、邮箱验证、OAuth authorize/token/revoke、OIDC discovery/JWKS、当前账号、Session 撤销、MFA、密码恢复、导出和注销。认证失败统一返回 `IDENTITY_INVALID_CREDENTIALS`，不得枚举用户。

内部 Agent API 保持冻结合同；本 Slice 不实现 Phase 3C–3J 业务端点。
