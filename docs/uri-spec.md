# awam:// URI 规范

扁平命名空间：后端作第一段，其后为该后端内路径或查询。

## 形式

```
awam://<backend>[/<path>][?<query>]
```

- scheme 固定 `awam`
- backend 小写字母数字与连字符
- path 使用 `/` 分隔；Windows 盘符写成 `G:/foo`（冒号保留）
- query 用于搜索类虚拟目录

## 第一期 backend

| Backend | 示例 | 说明 |
|---|---|---|
| `root` | `awam://` 或 `awam://root/` | 列出已注册后端 |
| `local` | `awam://local/G:/Projects` | 本机路径透传 |
| `search` | `awam://search/everything?q=readme` | Everything 搜索结果虚拟目录 |
| `rclone` | `awam://rclone/mysftp/var/www` | rclone remote（无挂载） |
| `knowledge` | `awam://knowledge/logseq-main/pages` | `G:\Knowledge\data\` 下图谱 |
| `downloads` | `awam://downloads/qb/` | qBittorrent 任务树 |
| `prowlarr` | `awam://prowlarr/search?q=ubuntu` | 索引搜索。结果条目是 `awam://prowlarr/item?...`，`resolve` 返回可直接交给下载器的 magnet 或种子字节 |
| `smb` | `awam://smb/` | 已映射共享与 `AWAM_SMB_ROOTS`，条目转到 `awam://local/unc/...` |
| `volumes` | `awam://volumes/images` | 已附加 VHD/ISO 与 `awam://volumes/drives` 盘符。不执行挂载 |
| `places` | `awam://places/recycle` | `recycle` / `recent` / `downloads` |
| `browser` | `awam://browser/edge/...` | Chrome / Edge 收藏夹（Bookmarks JSON）；`resolve` 返回 `open_url` |
| `hf` | `awam://hf/cache/` | 本地 hub；`awam://hf/remote?q=` 走 `HF_ENDPOINT` |
| `wsl` | `awam://wsl/<distro>/home` | `\\wsl.localhost\<distro>`。停止的发行版不会被启动 |
| `docker` | `awam://docker/<volume>` | 引擎未运行时 unavailable。VM 内挂载点只返回元数据 |
| `kopia` | `awam://kopia/` | CLI 不在或仓库未连接时 unavailable。不挂载快照 |
| `filehistory` | `awam://filehistory/` | 未启用文件历史时 unavailable |

## 操作语义

| 操作 | 含义 |
|---|---|
| `list` | 列目录 / 虚拟集合 |
| `stat` | 单条目元数据 |
| `read` | 读文本或小文件内容 |
| `search` | 跨后端或指定后端搜索 |
| `resolve` | URI → 本机 path 与/或外部动作（如 DOpus GO）；虚拟远程文件返回 `action: "download"` |
| `download` | 把虚拟文件落地为本机路径（虚拟后端）或直接返回已有本机路径（本地后端） |
| `backends` | 后端能力与健康状态 |

破坏性写操作（远端删除等）需显式 `allow_destructive=true`。

## download：虚拟文件落地

`POST /api/download`（或 `GET`，`?uri=`）返回 `DownloadResult`：

```json
{
  "uri": "awam://rclone/mysftp/var/www/app.txt",
  "local_path": "C:\\Users\\<user>\\Downloads\\awam-file\\mysftp\\app.txt",
  "backend": "rclone",
  "size": 1234,
  "ok": true,
  "truncated": false,
  "action": "downloaded",
  "error": null
}
```

- 本地后端（`knowledge` / `smb` / `wsl` / `volumes` / `places` / `hf` 缓存）：`resolve` 已有真实路径时直接返回，`action: "local"`，不复制。
- 虚拟后端（`rclone`）：`rclone copyto <spec> <下载目录>/<remote>/<文件名>`，二进制安全，`action: "downloaded"`。
- 下载根目录由 `AWAM_DOWNLOAD_DIR` 配置，默认 `~/Downloads/awam-file`；按 remote 建子目录避免同名冲突。
- 目录 / 根 URI 不可下载，`ok: false` + `error`。
- UI 接入端拿到 `local_path` 后在文件管理器中定位；本网关不负责打开文件。

## requiredQuery 与缺参软空态

搜索类虚拟目录在缺少必填查询参数时，`list` 返回软空态而非硬错误：

- `entries` 为空数组
- `error` 为 `null`
- `requiredQuery` 声明缺参，例如 `[{ "key": "q", "label": "Query", "required": true }]`

父目录列出这类子项时，子条目同样带 `requiredQuery`，便于 UI 在进入前展示查询框。有 `q` 时列表仍可附带 `requiredQuery`，方便界面回填。

适用：`awam://search/everything`、`awam://prowlarr/search`、`awam://hf/remote`。

## 与本机路径互转

- `awam://local/G:/a/b` ↔ `G:\a\b`
- `awam://knowledge/logseq-main/pages/x.md` ↔ `G:\Knowledge\data\logseq-main\pages\x.md`
- 搜索/下载虚拟条目若有保存目录，`resolve` 返回本机 path
