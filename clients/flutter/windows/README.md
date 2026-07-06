# Windows Runner

M2.5-A 预留 Windows 平台目录。当前 macOS 环境通常不能直接构建 Windows 桌面产物，且当前环境缺少 Flutter CLI，未生成完整 native runner。

在 Windows 开发机安装 Flutter SDK 后在 `clients/flutter` 执行：

```bash
flutter create --platforms=windows .
```
