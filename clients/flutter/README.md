<div align="center">

# reboot-health Flutter Client

### Natural language + action cards across mobile and desktop

<p>
  <img alt="Flutter" src="https://img.shields.io/badge/Flutter-Multi--platform-02569B?logo=flutter&logoColor=white">
  <img alt="Platforms" src="https://img.shields.io/badge/Targets-iOS%20%7C%20Android%20%7C%20macOS%20%7C%20Windows-0984E3">
  <img alt="Status" src="https://img.shields.io/badge/Status-Implemented%20with%20Blockers-E17055">
</p>

**reboot-health 的唯一正式用户客户端。**

</div>

## 🎯 Product role

Flutter Client 负责用户如何：

- 用自然语言表达目标、状态和反馈。
- 查看 AI 理解、计划草案和解释。
- 通过卡片确认、纠正或拒绝候选。
- 执行今日行动并提交反馈。
- 管理已配对设备和客户端凭据。

客户端只调用 Java Health Domain Kernel，不直接访问 Python Health Agent Harness。

## 🧭 Navigation

| 入口 | M2.5-A 状态 | 长期方向 |
|---|---|---|
| 今日 | Placeholder | 今日行动与完成反馈 |
| 教练 | Technical smoke test | 自然语言对话、AI 理解和建议 |
| 计划 | Placeholder | Program、Phase 与周计划 |
| 数据 | Placeholder | 趋势、Observation 与复盘 |
| 我的 | Implemented skeleton | 设备、隐私、提醒和个人资料 |

## ✅ Implemented in M2.5-A

- 五个主导航入口。
- 教练页创建 `AgentRun` 并轮询结构化卡片。
- bootstrap 首台设备初始化入口。
- 后续设备配对、设备列表、主设备标记和撤销入口。
- `SecureCredentialStore` 凭据抽象。
- access token 失效后自动 refresh 一次。
- 并发 401 使用 single-flight 合并刷新。
- 幂等写请求复用 `Idempotency-Key`。

## 🚧 Current blockers

当前记录的开发环境缺少 Flutter SDK，因此：

- 尚未生成真实 iOS、Android、macOS、Windows native runner。
- 尚未执行 `flutter analyze` 与 `flutter test`。
- 尚未验证多平台安全存储兼容性。
- 尚未完成真实 Flutter → Java → Python 端到端验收。

| Platform | Runner | Build verification |
|---|---|---|
| Android | `NOT GENERATED` | `NOT VERIFIED` |
| iOS | `NOT GENERATED` | `NOT VERIFIED` |
| macOS | `NOT GENERATED` | `NOT VERIFIED` |
| Windows | `NOT GENERATED` | `NOT VERIFIED` |

## 🛠️ Bootstrap native runners

安装 Flutter SDK 后，在本目录执行：

```bash
cd clients/flutter
flutter create --platforms=ios,android,macos,windows .
flutter pub get
```

生成后必须保留现有 `lib/`、`test/` 与项目配置，并检查平台安全存储配置。

## ✅ Verify

```bash
cd clients/flutter
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
flutter build ios --debug --no-codesign
flutter build macos --debug
```

Windows 构建必须在支持的 Windows 开发环境执行：

```powershell
flutter build windows --debug
```

## 🛡️ Client boundaries

- 不实现后端领域状态机。
- 不直接调用 Python Runtime。
- 不向普通用户展示 UUID、revision、PlanVersion 或内部枚举码。
- 不使用普通文件、SharedPreferences 或普通 SQLite 保存设备凭据。
- 不在日志中输出健康数据、配对码或认证信息。
- 不在 Vue 和 Flutter 中重复建设同一项正式业务能力。

详细规则见 [`AGENTS.md`](AGENTS.md)，系统架构见 [`../../docs/architecture.md`](../../docs/architecture.md)。
