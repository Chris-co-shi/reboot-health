<div align="center">

# Windows Runner

<img alt="Status" src="https://img.shields.io/badge/Status-Not%20Generated-D63031">
<img alt="Platform" src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white">

</div>

> 当前目录只是 M2.5-A 的平台占位，**不包含可构建的 Windows native runner**。

## Generate

在 Windows 开发机安装 Flutter SDK 与 Visual Studio Desktop C++ workload 后，从 `clients/flutter` 执行：

```powershell
flutter create --platforms=windows .
flutter doctor -v
flutter build windows --debug
```

macOS 环境不能替代真实 Windows 构建验收。完成后应删除本占位说明，并更新 [`../README.md`](../README.md)。
