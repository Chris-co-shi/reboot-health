# 跨服务合同

本目录是可机读跨服务合同的唯一共享存放位置，职责包括：

- Health Platform → `health-agent` Task Contract。
- `health-agent` → Health Platform Tool Contract。
- Runtime Event / Callback Contract。
- 后续 JSON Schema 与 OpenAPI 文件的共享位置。
- Schema 版本、兼容窗口和变更记录。

权威语义仍来自 [`../docs/API_CONTRACTS.md`](../docs/API_CONTRACTS.md)。服务不得各自维护语义不一致的合同副本。

本 Slice 不生成未经确认的 OpenAPI 或业务 payload Schema。后续合同必须版本化；灰度期间支持当前及前一兼容版本，破坏性变更采用 Expand–Migrate–Contract，未知枚举不得默认为安全值。
