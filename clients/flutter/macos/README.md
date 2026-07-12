<div align="center">

# macOS Runner

<img alt="Status" src="https://img.shields.io/badge/Status-Not%20Generated-D63031">
<img alt="Platform" src="https://img.shields.io/badge/Platform-macOS-000000?logo=apple&logoColor=white">

</div>

> 当前目录保留 Flutter macOS 工程基础；macOS 不是当前正式用户客户端交付目标。

## Verify

在安装 Flutter SDK 和 Xcode 后，从 `clients/flutter` 执行：

```bash
flutter doctor -v
flutter build macos --debug
```

如后续启用，必须检查 Keychain、entitlements 与 sandbox 配置。
