# Codex 仓库规则

## 适用范围

- 本文件适用于整个仓库。
- 修改 `backend/` 时，还必须遵守 `backend/AGENTS.md`。
- 修改 `frontend/` 时，还必须遵守 `frontend/AGENTS.md`。
- 用户当前提示中的直接要求优先于本文件。

## 通用工作规则

- 所有说明、计划、总结、自查和验收报告使用中文。
- 代码标识符、类名、方法名和字段名使用英文。
- 修改前先阅读本文件、当前目录相关 `AGENTS.md` 和任务相关文档。
- 不扩大任务范围；每个里程碑完成后停止并等待用户验收。
- 不为了测试通过而降低业务规则、删除测试、放宽断言或绕过校验。
- 不主动新增生产依赖；确需新增时先说明原因、替代方案和影响范围。
- 不在仓库中写入真实健康资料、真实密钥、真实数据库密码或本机绝对路径。

## 通用安全规则

- 本项目不做医学诊断，不替代医生意见。
- AI 只能生成计划草案或调整建议，不能直接发布或修改生效计划。
- 安全约束必须由确定性程序规则执行，不能只依赖 AI 提示词。
- 历史执行记录不得随计划版本变化而改变。
- 所有关键状态转换必须可审计、可测试。

## 验证命令

后端：

```bash
cd backend
mvn test
```

前端：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

部署配置：

```bash
docker compose -f deploy/docker-compose.yml config
```

## 完成定义

- 输出修改文件、新增文件、删除文件、核心说明、验证命令、验证结果、未完成事项和风险点。
- 涉及状态转换、数据库迁移、审计或安全规则时必须有自动化测试。
- 文档变更必须更新入口索引，并清理旧路径引用。

## 文档索引

- 产品范围：`docs/product-scope.md`
- 领域模型：`docs/domain-model.md`
- 架构方案：`docs/architecture.md`
- API 与数据库：`docs/api-db.md`
- 安全规则：`docs/safety-rules.md`
- MVP 执行计划：`docs/mvp-exec-plan.md`
- 未来 AI 调整设计：`docs/future/ai-adjustment.md`
- 架构决策记录：`docs/decisions/`
