# 0020 Identity、OAuth/OIDC 与 Session 安全

## 状态

已确认，2026-07-12 生效。

## Context

正式客户端与服务间调用需要可撤销用户会话、第一方 OAuth/OIDC、设备隔离、MFA 和恢复闭环。

## Decision

Identity 采用邮箱/用户名 + Argon2id、Authorization Code + PKCE、Refresh Token Rotation、Revocation、OIDC Discovery/JWKS/RS256 ID Token，以及 Client Credentials 的 RS256 服务 JWT。用户 Access/Refresh Token 为高熵不透明 Token，数据库仅保存哈希。每个设备独立 Session 与 Token Family；旧 Refresh Token 重放撤销整个 Family。高权限角色强制 TOTP + 一次性恢复码。用户 API 使用 `/api/v1`、snake_case、资源 DTO 直返；错误使用稳定 `error_code`。

## Alternatives

- JWT 用户 Access Token：即时撤销和权限版本失效更复杂。
- Password Grant：不适合第一方现代客户端。
- HS256 服务 Token：共享密钥扩大泄露半径。
- 短信 MFA：安全性和外部依赖不符合第一版。

## Consequences

需要授权码、Token Family、密钥轮换、缓存失效、审计及安全测试；OAuthLib 负责协议校验，FastAPI 只做薄适配。

## Security impact

固定算法、精确 Redirect URI、PKCE、state/nonce、一次性授权码、最小 scope/audience、MFA 和模糊登录错误阻断常见攻击。

## Migration impact

本 ADR 扩展并替代 `API_CONTRACTS.md` 旧统一外壳在 Health Platform `/api/v1` 的表达方式；内部 Agent 合同语义不变。未来破坏性变更进入 `/api/v2`。

## Superseded relationship

扩展 ADR 0012 的身份职责和 ADR 0016 的 Secret 边界；不改变 mTLS + 短期 JWT 服务间认证结论。

## Validation

注册/登录、PKCE、redirect、nonce、轮换/重放、撤销、MFA、枚举防护、JWKS 与固定算法测试。
