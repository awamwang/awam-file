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
| `prowlarr` | `awam://prowlarr/search?q=ubuntu` | 索引搜索。当前只使用搜索结果，不把结果送去下载 |
| `smb` | `awam://smb/` | 已映射共享与 `AWAM_SMB_ROOTS`，条目转到 `awam://local/unc/...` |
| `volumes` | `awam://volumes/images` | 已附加 VHD/ISO 与 `awam://volumes/drives` 盘符。不执行挂载 |
| `places` | `awam://places/recycle` | `recycle` / `recent` / `downloads` |
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
| `resolve` | URI → 本机 path 与/或外部动作（如 DOpus GO） |
| `backends` | 后端能力与健康状态 |

破坏性写操作（远端删除等）需显式 `allow_destructive=true`。

## 与本机路径互转

- `awam://local/G:/a/b` ↔ `G:\a\b`
- `awam://knowledge/logseq-main/pages/x.md` ↔ `G:\Knowledge\data\logseq-main\pages\x.md`
- 搜索/下载虚拟条目若有保存目录，`resolve` 返回本机 path
