# Identity 设计

Identity 负责账号、基础档案、邮箱验证、密码、登录风控、第一方 OAuth/OIDC、Session/设备、Token Family、MFA、恢复、RBAC、导出与注销任务。

用户名使用 Unicode casefold 规范化，邮箱使用 trim/lower 规范化并各自全局唯一。密码至少 12 位，Argon2id 哈希，常见/泄露密码通过可替换 Port 拒绝。未验证邮箱只获得受限 scope。

Access/Refresh Token 为随机不透明值，库内只存 SHA-256 哈希。刷新使用行锁和一次性轮换；已消费 Token 再次出现即撤销整个 Family并写安全事件。授权码绑定 client、redirect、scope、PKCE challenge、nonce，短期且一次性。

TOTP Secret 使用版本化字段加密；恢复码只展示一次并单独哈希。高权限角色必须完成 MFA。密码重置必须先通过邮件，安全问题只能辅助且答案哈希保存。
