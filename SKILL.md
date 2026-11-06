---
name: awam-file
description: >-
  Unified flat resource management via awam:// URIs. Gateway exposes local disk,
  Everything search, rclone remotes, Logseq knowledge under G:/Knowledge/data,
  qBittorrent downloads, and Prowlarr search. Same API for Sigma File Manager,
  Directory Opus jump, and AI (MCP).
---

# awam-file — 统一资源网关

一套 `awam://` URI + resource gateway，让 **Sigma File Manager（主）**、**Directory Opus（次）**、**AI（MCP）** 用相同语义访问本地盘、搜索、网盘、知识库与下载资源。

## 快速启动

```powershell
$env:PYTHONPATH = "G:\Projects\19AI\skills\awam-file\src"

# AI / Cursor：MCP stdio
python -m awam_resource_gateway mcp

# Sigma / 脚本：本机 HTTP（默认 127.0.0.1:18787）
python -m awam_resource_gateway http
# 已接入文件系统页面：http://127.0.0.1:18787/filesystems

# CLI
python -m awam_resource_gateway backends
python -m awam_resource_gateway list "awam://knowledge/"
python -m awam_resource_gateway search "readme" --backend search
python -m awam_resource_gateway open-dopus "awam://knowledge/logseq-main"
```

环境变量见 `src/awam_resource_gateway/config.py`。项目根目录的 `.env` 会在启动时读入，且已 gitignore；已经存在的环境变量优先于文件。Prowlarr 的 key 写在 `.env` 的 `AWAM_PROWLARR_API_KEY`，不要写进仓库。

## URI 一览

详见 [docs/uri-spec.md](docs/uri-spec.md)。

| URI | 用途 |
|---|---|
| `awam://root/` | 后端目录 |
| `awam://local/G:/path` | 本机路径 |
| `awam://local/unc/server/share` | UNC，对应 `\\server\share` |
| `awam://search/everything?q=term` | Everything 结果虚拟目录 |
| `awam://rclone/<remote>/...` | 任意已配置的 rclone remote，不用改代码 |
| `awam://knowledge/logseq-main/...` | 知识库；`_flat` 为扁平页面视图 |
| `awam://downloads/qb/` | qBittorrent（需开启 WebUI） |
| `awam://prowlarr/search?q=` | Prowlarr 搜索；结果是 `awam://prowlarr/item?...` |
| `awam://smb/` | 已映射共享和 `AWAM_SMB_ROOTS` |
| `awam://volumes/images` | 已附加的 VHD/ISO |
| `awam://volumes/drives` | 当前盘符 |
| `awam://places/recycle` | 回收站 |
| `awam://places/recent` | 最近使用 |
| `awam://places/downloads` | 用户与 Public 下载目录 |
| `awam://hf/cache/` | Hugging Face 本地 hub 缓存 |
| `awam://hf/remote?q=` | 模型搜索，地址来自 `HF_ENDPOINT` |
| `awam://wsl/<distro>/` | 仅列出；停止的发行版不会被启动 |
| `awam://docker/` | 引擎已运行时的 volume 元数据 |
| `awam://kopia/` | 有 CLI 且仓库已连接时列快照 |
| `awam://filehistory/` | 文件历史已启用时给出目标路径 |

## MCP 工具

`res_backends` / `res_list` / `res_stat` / `res_read` / `res_search` / `res_resolve` / `res_open_in_dopus` / `res_push_to_downloads`

已在 awam-tool-manager 注册为 `awam-resource-gateway`。

## Sigma

Home 页有 **Awam Resources** 入口；地址栏可进 `awam://...`；全局搜索会合并 Everything（经网关）。  
需先起 HTTP：`python -m awam_resource_gateway http`。  
可选：`VITE_AWAM_GATEWAY_URL=http://127.0.0.1:18787`。

## Directory Opus

```powershell
.\scripts\open_in_dopus.ps1 "awam://knowledge/logseq-main"
# 或
python -m awam_resource_gateway open-dopus "G:\Knowledge\data\logseq-main"
```

解析出本机路径后调用 `dopusrt.exe /cmd Go "..."`.

## 前置条件备忘

- Everything + `es.exe`：已用于搜索
- rclone：配好 remote 后 `awam://rclone/<name>/` 直接可列、可 `cat` 小文件。挂载不是前提。
- qBittorrent：可以浏览已有任务。当前阶段不把 Prowlarr 搜索结果送去下载。
- Prowlarr：只取搜索结果。`AWAM_PROWLARR_API_KEY` 放在本机 `.env`，不写入仓库。
- SMB：已映射的共享会被发现。没有盘符的 UNC 可以选填本机环境变量 `AWAM_SMB_ROOTS`，不写进项目。
- Hugging Face 镜像：沿用环境变量 `HF_ENDPOINT`，不在代码里写死。
