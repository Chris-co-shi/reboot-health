# Phase 3B Slice 2：工具链恢复与结构整改验收计划

## Summary

本轮不新增业务能力，只做两件事：

1. 修复上一轮结构整改中遗留的「`IdentityError` 处理器被注册在 `APIRouter` 上」问题——按任务字面要求，必须由 FastAPI **app** 显式注册。
2. 恢复 uv 工具链与 Python 3.12 解释器，验收上一轮结构整改：跑 `tests/test_api.py` / Identity 单测 / background 测试 / Ruff / Mypy；如环境允许跑 PostgreSQL 集成测试与 health-agent 回归。

完成后把工具链来源、实际命令、测试数量、失败与未验证项写回 `docs/PHASE_STATUS.md` 与 Slice 2 完成记录；Phase 3B Slice 2 仍保持 `IN_PROGRESS`。

---

## Current State Analysis

### 已完成（上一轮）

- 删除顶层 5 个空骨架包：`health_platform/{adapters,application,domain,interfaces,ports}/__init__.py`。
- 删除 8 个 SKELETON 模块（conversation / fact / goal / plan / risk / file / secret / agent_integration）的 5 层空子包与重复 `AGENTS.md`；保留 `README.md`；新增 `modules/AGENTS.md` 通用骨架规则。
- 新增 `modules/identity/interfaces/{__init__.py,http.py}`：把 DTO、`principal` 依赖、Identity/OAuth/OIDC/JWKS 路由原样迁入 `build_identity_router()`。
- `platform/web/app.py` 瘦化为 Composition Root，保留 `create_app` / `_local_jwt_keys` / `_register_default_oauth_clients` / `lifespan` / Probe / `include_router(prefix="/api/v1")`。
- 文档：`docs/PHASE_STATUS.md`、`docs/design/health-platform/MODULES.md`、`docs/design/health-platform/FEATURE_MATRIX.md`、`docs/implementation/phase-3b-slice-2-*.md` 已同步结构改动记录。

### 残留问题（本轮须修复）

- `modules/identity/interfaces/http.py:125` 仍然调用 `router.add_exception_handler(IdentityError, _identity_error_handler)`；按任务字面要求应改为「FastAPI app 显式注册」，否则违反任务约束。运行不会失败（FastAPI 0.115 `APIRouter` 支持 `add_exception_handler`），但语义上仍属于违规写法。

### 环境现状

- `/usr/local/bin/python3.12` 存在（系统解释器）。
- `/Users/sxc/Library/Application Support/uv/python/cpython-3.13-macos-aarch64-none/bin/python3.13` 已存在 uv 管理版本。
- `health_agent/.venv/bin/python` 是 cpython-3.13，但 `pip` 模块缺失，无法直接安装第三方包；需要用 `uv` 或重新创建 venv。
- `uv` 二进制不在 PATH；可用 `pip3 install --user uv` 安装，或使用 `python3 -m ensurepip --user` 间接引导。
- Docker / Testcontainers 是否可用待运行 `docker version` 时确认。

### 行为不变量（必须保持）

- 所有 `/api/v1/identity/*`、`/api/v1/oauth/{token,authorize,revoke}`、`/api/v1/.well-known/{openid-configuration,jwks.json}`、`/health/{live,startup,ready}` 路径一字不变。
- `OAuthClient.audience == "health-platform-api"` 不变。
- `IdentityError → 401/400 + error_code/message/trace_id/details` 响应结构不变。

---

## Proposed Changes

### 1. 修复 IdentityError handler 注册位置

**文件**：`health_platform/src/health_platform/modules/identity/interfaces/http.py`

- 删除 `_identity_error_handler` 函数体（94–111 行）与 `router.add_exception_handler(IdentityError, _identity_error_handler)` 调用（125 行）。
- 在该模块中保留可导出的 `identity_error_handler` 函数（与 `_` 前缀解耦），仅供 Composition Root 注册，不在 router 上注册。

**文件**：`health_platform/src/health_platform/platform/web/app.py`

- 新增 `from health_platform.modules.identity.interfaces.http import build_identity_router, identity_error_handler`。
- 在 `create_app` 创建 `FastAPI` 实例后、`include_router` 之前，调用 `app.add_exception_handler(IdentityError, identity_error_handler)`。
- 新增 `from health_platform.modules.identity.domain.models import IdentityError`。

**验收**：`tests/test_api.py::test_login_enumeration_error_model_is_stable` 仍然 401、`error_code == "IDENTITY_INVALID_CREDENTIALS"`、`"trace_id" in response.json()` 通过；其余 `test_api.py` 测试路径不变。

### 2. 工具链恢复（uv + Python 3.12 venv）

按以下顺序执行（失败则降级并如实标记）：

```bash
# 步骤 A：定位 uv
which uv || command -v uv || ls "$HOME/.local/bin/uv"
# 若无 uv，使用系统 pip 安装到 user 目录
python3 -m pip install --user uv || python3 -m ensurepip --user && python3 -m pip install --user uv
# 加入 PATH
export PATH="$HOME/.local/bin:$PATH"
uv --version

# 步骤 B：建立 health_platform venv（Python 3.12 系统解释器）
cd "/Users/sxc/company/IndigoByte Studios/reboot-health"
uv venv --python /usr/local/bin/python3.12 health_platform/.venv
source health_platform/.venv/bin/activate
uv sync --project health_platform

# 步骤 C：补 health_agent venv（修复缺 pip 的问题）
cd "/Users/sxc/company/IndigoByte Studios/reboot-health/health_agent"
uv venv --python /Users/sxc/Library/Application\ Support/uv/python/cpython-3.13-macos-aarch64-none/bin/python3.13 .venv
# 若 .venv 已存在且可用，则跳过创建；否则保留并同步依赖
uv sync
```

### 3. 运行验收

```bash
cd "/Users/sxc/company/IndigoByte Studios/reboot-health/health_platform"
source ../health_platform/.venv/bin/activate

# 1) 静态语法 + 导入自检
python3 -m compileall -q src
python3 -c "from health_platform.platform.web.app import create_app; app = create_app(); schema = app.openapi(); print(sorted(schema['paths'].keys()))"
# 期望：/api/v1/identity/{deletion-requests,email-verifications/confirm,exports,login,mfa/recover,mfa/totp/confirm,mfa/totp/enroll,me,password-recovery,password-recovery/complete,register}, /api/v1/oauth/{authorize,revoke,token}, /api/v1/.well-known/{jwks.json,openid-configuration}, /health/{live,ready,startup}；且无重复前缀。

# 2) Ruff + Mypy
ruff check .
mypy

# 3) 单元测试（不含 PostgreSQL 集成）
pytest -q -m "not postgres" --maxfail=1

# 4) PostgreSQL 集成（环境允许时）
docker version >/dev/null 2>&1 && pytest -q -m postgres --maxfail=1 || echo "postgres integration skipped: docker not available"

# 5) health-agent 回归
cd ..
source health_agent/.venv/bin/activate
python3 -m compileall agent tests
python3 -m unittest discover -s tests -v
```

### 4. 文档更新

**文件**：`docs/implementation/phase-3b-slice-2-health-platform-production-foundation.md`

在"本轮结构整改"段后追加"本轮验收"段：
- Python/uv 来源：`/usr/local/bin/python3.12` + `~/.local/bin/uv`（如从 user 装）。
- 实际命令：`uv venv --python /usr/local/bin/python3.12` + `uv sync --project health_platform` + 上述 5 条验收。
- 测试结果：单元测试数、PostgreSQL 测试是否执行、Ruff/Mypy 是否通过、health-agent 回归数。

**文件**：`docs/PHASE_STATUS.md`

Slice 2 完成证据段落补一行：工具链恢复 + 验收命令 + 测试通过/失败统计 + 未验证项。

---

## Assumptions & Decisions

1. **handler 移至 app 级**：任务原文「异常处理必须由 FastAPI app 显式注册，不得假设 APIRouter 支持全局 exception handler」。本轮默认采用「删除 router 级注册 + app 显式 `add_exception_handler`」。
2. **Python 解释器版本**：使用 `/usr/local/bin/python3.12`（已存在），与 `requires-python = ">=3.12"` 对齐，避免重装。
3. **uv 安装位置**：若 `uv` 不在 PATH，尝试 `python3 -m pip install --user uv`；失败则尝试 `pip3 install --user uv`；最终降级为记录「uv 不可用」。
4. **PostgreSQL 集成测试**：默认尝试；`docker version` 失败则跳过并标记 `skipped: docker not available`。
5. **health-agent 回归**：使用 `uv sync` 重建 `.venv`（保留原 `.venv` 配置）；如 `uv sync` 失败，使用原 `.venv/bin/python` 直接运行 `compileall` + `unittest`。
6. **不修改任何业务代码、数据库、API、Schema**：与任务边界一致。
7. **保持 IN_PROGRESS**：按 §15，验收未完成全部 DoD 前不得标 `DONE`。

---

## Verification Steps

执行下列命令并把实际输出贴回报告：

| 序号 | 命令 | 期望 |
|---|---|---|
| V1 | `uv --version` | 输出版本号；缺失则安装并重试 |
| V2 | `python3 -m compileall -q src` | 退出码 0，无输出 |
| V3 | `python3 -c "from health_platform.platform.web.app import create_app; ..."` | 路径集合含上述全部路径且无重复前缀 |
| V4 | `ruff check .` | 退出码 0 或仅有与本轮无关的既有告警 |
| V5 | `mypy` | 退出码 0 或仅有既有 strict 告警 |
| V6 | `pytest -q -m "not postgres"` | 全部通过；统计 N 项 |
| V7 | `docker version` + `pytest -q -m postgres` | 失败则标记 `skipped` |
| V8 | health-agent `compileall` + `unittest discover` | 全部通过；统计 N 项 |

---

## Out of Scope

- 生产 SQL Composition Root、OAuthLib 闭环、Redis IP/设备限流、MFA 关闭/重置、固定安全问题、权限管理用例、SMTP Outbox Processor、OTel instrumentation、数据库/Alembic readiness、并发 Refresh/幂等和审计不可变集成测试。
- 任何新功能；任何对业务行为、API 路径、状态码、响应模型、OpenAPI 的修改。
- `health_agent/agent/**`、`health_agent/tests/**` 源码改动（仅跑现成测试）。

## Risks

1. 工具链恢复需要网络；如离线或无 `pip`，只能标记「未验证」。
2. `/usr/local/bin/python3.12` 在 Apple Silicon 上可能不存在；任务允许降级使用 `/usr/local/bin/python3.9` 系统的 Python 3.9，但 `requires-python = ">=3.12"` 会阻断 `uv sync`，需如实标记。
3. health_agent `.venv` 的 `pip` 缺失可能在 `uv sync` 时被修复；若失败，必须改用 `health_platform/.venv` 跑 health-agent 回归（依赖冲突需如实标记）。
4. Docker 不可用时，4 项 PostgreSQL 集成测试必须跳过；不得伪造通过。
5. 修改 `IdentityError` handler 注册位置需要同步更新 `tests/test_api.py` 的预期吗？不需要——`tests/test_login_enumeration_error_model_is_stable` 只断言 `status_code==401` 与 `error_code=="IDENTITY_INVALID_CREDENTIALS"`，handler 位置不影响断言。