# 安全设计

认证采用不透明用户 Token、RS256 ID/服务 Token、精确 Redirect URI、S256 PKCE、state/nonce 和固定算法。授权集中于 Application Policy，结合 RBAC、资源归属和关系授权；系统管理员不自动获得健康原文权限。

字段加密使用 AES-256-GCM 信封格式，密钥版本来自只读 Kubernetes Secret 挂载；current 可加解密，historical 仅解密。私钥、主密钥、Token、密码、TOTP、恢复码和完整联系方式不得进入日志、响应或 Git。

PostgreSQL RLS 是第二道防线；Redis 故障回退数据库且不放行未知 Token。审计只追加并使用前一哈希形成链。
