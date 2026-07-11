# 文档治理规则

## 1. 架构状态

```text
FROZEN since 2026-07-12
```

`docs/README.md` 列出的文档是唯一事实来源。旧文件名、旧 Phase 路线、聊天摘要和代码注释不能覆盖冻结文档。

## 2. 唯一职责

- 产品和用户体验：`PRODUCT_REQUIREMENTS.md`
- 服务、组件、数据流和信任边界：`SYSTEM_ARCHITECTURE.md`
- 领域对象和不变量：`DOMAIN_MODEL.md`
- 状态与转换：`STATE_MACHINES.md`
- API、事件、幂等和错误合同：`API_CONTRACTS.md`
- 身份、Sandbox、Secret、隐私和删除：`SECURITY_AND_PRIVACY.md`
- Kubernetes、存储、灰度、备份、监控和恢复：`DEPLOYMENT_AND_OPERATIONS.md`
- 阶段、状态、验收、阻塞和路线：`PHASE_STATUS.md`
- 重大决策：`decisions/`
- 已批准 Slice 的工程交接：`implementation/`

相同事实只允许在一个文档中完整定义，其他文档链接或摘要。

## 3. 优先级

```text
已批准 ADR
→ 产品/安全
→ 架构/领域
→ 状态机/API
→ 部署运维
→ Phase/implementation
→ 代码、测试、提示词
```

ADR 结论必须同步到主文档。只更新 ADR 不算完成变更。

## 4. Architecture Freeze 变更流程

任何架构变化必须：

1. 写明背景、替代方案和影响。
2. 新增或更新 ADR。
3. 更新所有受影响权威文档。
4. 更新 `PHASE_STATUS.md`。
5. 用户人工批准。
6. 批准后才能创建 implementation 规范和代码任务。

禁止用代码、数据库迁移、K8s YAML、Issue、PR 或提示词反向修改架构。

## 5. Implementation 规范

`implementation/` 只保存 `READY` 或 `IN_PROGRESS` Slice。

必须包含：

- Phase/Slice。
- Primary Module。
- Authoritative Documents。
- Allowed/Forbidden Paths。
- Contract Changes。
- Migration/Compatibility。
- Required Verification。
- Definition of Done。
- Out of Scope。
- Completion Report Template。

不得：

- 自己声明完成。
- 重复或修改长期架构。
- 一次实现整个 Phase。
- 提前实现后续能力。
- 将技术 Spike 结果直接写成已批准决策。

## 6. 状态表达

状态以 `PHASE_STATUS.md` 定义为准。

- 没有真实验收不能写 `DONE`。
- 文档完成不能代表代码完成。
- 代码存在但默认路径未接入时使用 `DONE_EXPLICIT` 或 `IMPLEMENTED_WITH_BLOCKERS`。
- 医学阈值没有专业审核时使用 `NEEDS_MEDICAL_REVIEW`。

## 7. 删除和历史

- 被新体系替代的重复权威文档应删除，历史通过 Git 追溯。
- 历史 ADR 保留，但必须明确已替代/历史状态。
- 完成阶段的临时 implementation 规范在证据汇总到 `PHASE_STATUS.md` 后可以删除。
- legacy 代码不属于文档治理任务；删除前必须有独立迁移 Slice 和验收。
- 删除文件时必须更新所有 README、AGENTS 和相对链接。

## 8. 提示词

任何实施提示词都必须引用：

- `AGENTS.md`
- `docs/README.md`
- `docs/PHASE_STATUS.md`
- 相关权威文档和 ADR
- 当前 implementation 规范

提示词不得重新叙述一套与文档不同的架构。发现冲突必须停止并报告。

## 9. 隐私

文档示例不得包含：

- 真实健康资料。
- 真实 API Key、Token、密码或证书。
- 本机绝对路径和真实内部地址。
- 完整 Prompt、隐藏推理或敏感 Tool 原文。

## 10. 验证

文档变更至少检查：

- 相对链接。
- 旧文件名和旧 Phase 名是否仍被当前文档引用。
- ADR 状态和替代关系。
- 当前实现事实与 `PHASE_STATUS.md` 是否一致。
- 不同文档中状态名、服务名和字段语义是否冲突。
- `git diff --check`。

文档治理任务不得修改业务代码、数据库 Schema 或 Kubernetes 清单。
