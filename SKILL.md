---
name: awam-file
description: >-
  Unified flat resource management via awam:// URIs. Gateway exposes local disk,
  Everything search, rclone remotes, Logseq knowledge under G:/Knowledge/data,
  qBittorrent downloads, and Prowlarr search stubs. Same API for Sigma File Manager,
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

# CLI
python -m awam_resource_gateway backends
python -m awam_resource_gateway list "awam://knowledge/"
python -m awam_resource_gateway search "readme" --backend search
python -m awam_resource_gateway open-dopus "awam://knowledge/logseq-main"
```

环境变量见 `src/awam_resource_gateway/config.py`（`AWAM_KNOWLEDGE_ROOT`、`AWAM_QB_*`、`AWAM_PROWLARR_*`、`AWAM_GATEWAY_PORT` 等）。

## URI 一览

详见 [docs/uri-spec.md](docs/uri-spec.md)。

| URI | 用途 |
|---|---|
| `awam://root/` | 后端目录 |
| `awam://local/G:/path` | 本机路径 |
| `awam://search/everything?q=term` | Everything 结果虚拟目录 |
| `awam://rclone/<remote>/...` | rclone（先 `rclone config`） |
| `awam://knowledge/logseq-main/...` | 知识库；`_flat` 为扁平页面视图 |
| `awam://downloads/qb/` | qBittorrent（需开启 WebUI） |
| `awam://prowlarr/search?q=` | Prowlarr（未安装时 unavailable） |

## MCP 工具

`res_backends` / `res_list` / `res_stat` / `res_read` / `res_search` / `res_resolve` / `res_open_in_dopus`

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
- rclone：需自行 `rclone config` 添加 remote（挂载非必须）
- qBittorrent：设置 → Web UI → 启用（默认探测 `http://127.0.0.1:8080`）
- Prowlarr：恢复安装后设 `AWAM_PROWLARR_API_KEY`
