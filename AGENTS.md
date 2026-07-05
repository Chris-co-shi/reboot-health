# Codex 项目规则

## 每次必须遵守

- 所有说明、计划、总结和自查结果使用中文。
- 修改前先阅读本文件，以及本次任务直接相关的 `docs/` 文档。
- 未经用户确认，不编写业务代码、不新增生产依赖、不扩大任务范围。
- 不为了测试通过而降低业务规则、删除测试、放宽断言或绕过校验。
- AI 相关实现必须遵守：AI 只能生成建议，不能直接发布或修改生效计划。
- 安全规则必须由确定性程序执行，不能只依赖提示词。

## 构建与验证命令

后端：

```bash
cd backend
/Users/sxc/Documents/tool/apache-maven-3.9.0/bin/mvn test
```

前端：

```bash
cd frontend
pnpm install
pnpm run typecheck
pnpm run build
```

部署配置：

```bash
docker compose -f deploy/docker-compose.yml config
```

## 验收规则

- 每个里程碑必须可运行、可人工验收。
- 每次完成后输出：修改文件、新增文件、删除文件、核心说明、验证命令、验证结果、未完成事项、风险点。
- 涉及关键状态转换时必须有测试。
- 文档任务至少检查文件清单和 OPEN 未确认事项。

## 文档索引

- 产品范围：`docs/product-scope.md`
- 领域模型：`docs/domain-model.md`
- 架构方案：`docs/architecture.md`
- AI 调整设计：`docs/ai-adjustment-design.md`
- 安全规则：`docs/safety-rules.md`
- MVP 执行计划：`docs/mvp-exec-plan.md`
- 架构决策记录：`docs/decisions/`
- API 与数据库草案：`docs/api-db-draft.md`
