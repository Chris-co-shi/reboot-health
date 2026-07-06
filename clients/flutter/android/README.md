<div align="center">

# Android Runner

<img alt="Status" src="https://img.shields.io/badge/Status-Not%20Generated-D63031">
<img alt="Platform" src="https://img.shields.io/badge/Platform-Android-3DDC84?logo=android&logoColor=white">

</div>

> 当前目录只是 M2.5-A 的平台占位，**不包含可构建的 Android native runner**。

## Generate

在安装 Flutter SDK 和 Android toolchain 后，从 `clients/flutter` 执行：

```bash
flutter create --platforms=android .
flutter doctor -v
flutter build apk --debug
```

完成后应删除本占位说明，并以真实 runner 配置和构建结果更新 [`../README.md`](../README.md)。
