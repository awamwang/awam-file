# 浏览器书签后端

`awam://browser/` 由 `BrowserAdapter` 提供。AFM / Sigma 等客户端只消费网关 API，不各自解析 Bookmarks 文件。

## URI 形状

```
awam://browser/{product}/{profileDir}/{rootKey}/{nodeId}/...
```

| 段 | 含义 | 例 |
|---|---|---|
| product | Reader id | `edge` / `chrome` |
| profileDir | 磁盘档案目录名 | `Default` / `Profile 1` |
| rootKey | Chromium roots 键 | `bookmark_bar` / `other` / `synced` |
| nodeId | 书签或文件夹 id | `10` |

叶子 URL 节点：`list`/`stat` 的 `extra.url` + `extra.kind=bookmark`；`resolve` 返回 `action=open_url`、`action_args.url`。

## 已注册 Reader

| id | 显示名 | 格式 | 本机路径（Windows） |
|---|---|---|---|
| `edge` | Microsoft Edge | Chromium `Bookmarks` JSON | `%LOCALAPPDATA%\Microsoft\Edge\User Data` |
| `chrome` | Google Chrome | Chromium `Bookmarks` JSON | `%LOCALAPPDATA%\Google\Chrome\User Data` |

共享解析在 `adapters/browser/readers/chromium.py`。

## 新增浏览器（小适配）

1. 实现 `BrowserReader`（`id` / `display_name` / `discover_profiles` / `bookmarks_doc`）。
2. 若格式与 Chromium 不同（如 Firefox `places.sqlite`），自行产出可被适配器映射的结构，或在 `BrowserAdapter` 增加对应 list/resolve 分支；优先保持 URI 段语义一致。
3. 在 `readers/__init__.py` 的 `default_readers()` 注册。
4. 本文件补一行；加 fixture 测试。

不必改 AFM：网关 `/api/backends` 会动态发现 `browser`。

## 与 AFM 应用内「收藏夹」的区别

- **本后端**：各浏览器产品收藏夹（Bookmarks）。
- **AFM `favorites.json`**：应用内文件夹钉选，仍留在 AFM，不经过本适配器。
