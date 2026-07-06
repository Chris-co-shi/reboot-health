<div align="center">

# macOS Runner

<img alt="Status" src="https://img.shields.io/badge/Status-Not%20Generated-D63031">
<img alt="Platform" src="https://img.shields.io/badge/Platform-macOS-000000?logo=apple&logoColor=white">

</div>

> 当前目录只是 M2.5-A 的平台占位，**不包含可构建的 macOS native runner**。

## Generate

在安装 Flutter SDK 和 Xcode 后，从 `clients/flutter` 执行：

```bash
flutter create --platforms=macos .
flutter doctor -v
flutter build macos --debug
```

完成后应删除本占位说明，并检查 Keychain、entitlements 与 sandbox 配置，再更新 [`../README.md`](../README.md)。
