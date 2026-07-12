<div align="center">

# iOS Runner

<img alt="Status" src="https://img.shields.io/badge/Status-Not%20Generated-D63031">
<img alt="Platform" src="https://img.shields.io/badge/Platform-iOS-000000?logo=apple&logoColor=white">

</div>

> 当前目录保留 Flutter iOS 工程基础；真实构建能力以本 Slice 的验证记录为准。

## Verify

在安装 Flutter SDK、Xcode 和 CocoaPods 后，从 `clients/flutter` 执行：

```bash
flutter doctor -v
flutter build ios --debug --no-codesign
```

正式能力必须只调用 Health Platform，并检查 Keychain、entitlements 与签名配置。
