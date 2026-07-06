# reboot-health Flutter Client

Flutter 是 `reboot-health` 的正式主客户端。M2.5-A 只提供四端最小骨架、设备初始化/配对入口和 AgentRun 技术链路检查。

## 范围

- 五个主导航：今日、教练、计划、数据、我的。
- 教练页调用 Java 后端创建 `AgentRun`，轮询展示结构化卡片。
- 我的页提供 bootstrap 初始化、后续设备配对、设备列表、主设备标记和撤销入口。
- 凭据通过 `SecureCredentialStore` 抽象保存，具体实现使用 `flutter_secure_storage`。
- API 客户端在 access token 过期时自动 refresh 一次，并使用 single-flight 避免并发重复刷新。
- 不直接调用 Python Agent Runtime。
- 不实现 M2.5-B/C 的自然语言访谈、计划生成、DailyAction 或 Observation。

## 本地命令

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
flutter build ios --debug --no-codesign
flutter build macos --debug
flutter build windows --debug
```

当前执行环境没有 `flutter` 命令，因此尚未生成平台 native runner，也尚未验证 `flutter_secure_storage` 在 iOS、Android、macOS、Windows 四端的实际兼容性。安装 Flutter SDK 后可在本目录执行：

```bash
flutter create --platforms=ios,android,macos,windows .
```

随后保留 `lib/`、`test/` 和当前配置文件，再执行上述验证命令。
