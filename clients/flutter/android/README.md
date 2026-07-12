<div align="center">

# Android Runner

<img alt="Status" src="https://img.shields.io/badge/Status-Not%20Generated-D63031">
<img alt="Platform" src="https://img.shields.io/badge/Platform-Android-3DDC84?logo=android&logoColor=white">

</div>

> 当前目录保留 Flutter Android 工程基础；真实构建能力以本 Slice 的验证记录为准。

## Verify

在安装 Flutter SDK 和 Android toolchain 后，从 `clients/flutter` 执行：

```bash
flutter doctor -v
flutter build apk --debug
```

不得在 Runner 中直接接入 `health-agent` 或基础设施。
