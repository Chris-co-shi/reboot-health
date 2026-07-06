# Vue 内部调试工具规则

## 定位

`frontend/` 已冻结为内部调试工具，不再承担正式产品体验。正式客户端是 `clients/flutter/`。

## 允许修改

- 修复阻塞 M2A/M2B 数据查看或人工验收的问题。
- 适配后端已确认的接口变更。
- 修复类型、构建、安全或明显显示错误。
- 增加仅用于内部排障的最小信息，但必须与普通用户产品隔离。

## 禁止修改

- 不新增 Agent、Program、Phase、DailyAction、Observation 等正式业务页面。
- 不在 Vue 和 Flutter 中双重实现新产品功能。
- 不把 Vue 恢复为主客户端或管理后台产品。
- 不因调试方便绕过设备认证、状态机、幂等或审计。
- 不新增复杂权限、营销首页或通用后台框架。

## 技术规则

- 使用 Vue 3 Composition API 与 `<script setup lang="ts">`。
- TypeScript 保持 strict，禁止 `any`。
- API 调用统一经过 services 层。
- API 模型、表单模型和展示模型按需区分。
- 后端是业务状态机最终权威。
- 不直接展示内部枚举码、UUID、revision 或技术堆栈。
- 不在控制台输出健康数据或认证信息。
- 不可逆操作必须二次确认。
- 表单默认值不得伪装成用户真实数据。

## 验证

仅在修改本目录时执行：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

Vue 构建通过不代表正式 Flutter 客户端已验收。