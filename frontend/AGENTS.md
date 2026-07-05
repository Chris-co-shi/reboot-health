# 前端 Coding Rules

## Vue 3

- 使用 Composition API 和 `<script setup lang="ts">`。
- 页面组件负责流程编排，可复用业务逻辑提取为 composable，可复用 UI 提取为 component。
- 不把所有逻辑堆在单个 View 中。
- Pinia 只用于真正跨页面共享的状态，局部表单状态不进入 Pinia。
- 路由页面优先使用动态 import 懒加载。
- 列表必须有稳定 key；不在模板中编写复杂业务表达式；不直接修改 props。
- 组件 props 和事件必须显式类型化。

## TypeScript

- 保持 strict，禁止 `any`。
- 禁止无说明的类型断言和滥用非空断言。
- 使用 type-only import。
- API 模型、表单模型和页面展示模型按需区分。
- 状态和枚举优先使用联合类型；穷举状态使用 `never` 检查。
- 后端枚举值和中文显示文本分离，不在页面直接展示内部枚举。
- 日期和时区语义必须明确，浏览器时区使用 `Intl.DateTimeFormat().resolvedOptions().timeZone`。
- 后端始终是业务状态机最终权威。

## API 调用

- API 调用统一经过 `services` 层，不在 Vue 页面中直接 `fetch`。
- API 客户端必须处理 JSON 响应、空响应、网络异常、HTTP 错误和后端字段校验错误。
- 页面必须能显示后端 `fields` 对应的表单错误。
- 不吞异常，不向用户显示原始堆栈，不在控制台输出健康数据。
- 请求和响应类型必须明确。

## 表单和交互

- Element Plus 表单必须使用 `FormInstance` 和 `FormRules` 做基础校验。
- 提交前必须调用 `validate()`，后端仍执行最终业务校验。
- 归档、取消、完成等不可逆操作必须二次确认。
- 终态数据不得展示可编辑入口。
- 按钮可用性必须与状态机一致。
- 枚举使用集中 label 映射。
- 表单默认值不得伪装为用户真实数据。
- 加载、空数据、失败和提交中状态必须明确，重复提交必须通过 loading 防止。

## 注释

- 导出的 composable、公共组件、API 客户端、非直观状态映射、表单归一化逻辑、兼容降级逻辑和不可逆操作原因必须有中文注释或 TSDoc。
- 禁止给明显模板结构添加噪音注释，禁止使用过期注释。

## 验证

当前不新增 Vitest、Vue Test Utils 或 E2E 依赖。必须执行：

```bash
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```
