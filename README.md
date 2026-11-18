# awam-file

[![Publish preflight](https://github.com/awamwang/awam-file/actions/workflows/publish-check.yml/badge.svg)](https://github.com/awamwang/awam-file/actions/workflows/publish-check.yml)

A unified resource gateway built around `awam://` URIs. It exposes local disks, Everything search, rclone remotes, a Logseq knowledge base, qBittorrent downloads, and several other sources behind one consistent API — so file managers and AI agents can all talk to the same set of resources with the same semantics.

Clients that speak this API today:

- **Sigma File Manager** (primary) — home-page entry plus `awam://...` in the address bar
- **A File Manager Providers** — dynamic backend discovery via `/api/backends`
- **Directory Opus** (secondary) — jump to a resolved local path
- **AI agents** — through the MCP stdio server

## Features

- One flat URI namespace covering local paths, UNC shares, search results, cloud remotes, knowledge pages, downloads and more.
- Three surfaces over the same core: MCP (stdio), a localhost HTTP API, and a CLI.
- Virtual backends (for example rclone) can materialize a file into a local download directory on demand.
- Backend health and capability discovery at runtime — no client-side hardcoding of what exists.
- Destructive remote operations are gated behind an explicit `allow_destructive=true` flag.

## Requirements

- Python 3.11 or newer
- Optional external tools, only for the backends that use them: Everything (`es.exe`), rclone, qBittorrent (WebUI), Prowlarr, Docker, WSL, kopia, Directory Opus. Backends degrade gracefully when their tool is unavailable.

## Installation

```bash
pip install -e .
```

Or run directly from a checkout with `src` on the import path:

```bash
export PYTHONPATH=src        # Windows PowerShell: $env:PYTHONPATH = "src"
python -m awam_resource_gateway --help
```

## Usage

MCP stdio server (for AI clients):

```bash
python -m awam_resource_gateway mcp
```

Localhost HTTP server (default `127.0.0.1:18787`):

```bash
python -m awam_resource_gateway http
# UI: http://127.0.0.1:18787/filesystems
```

CLI examples:

```bash
python -m awam_resource_gateway backends
python -m awam_resource_gateway list "awam://knowledge/"
python -m awam_resource_gateway search "readme" --backend search
python -m awam_resource_gateway open-dopus "awam://knowledge/logseq-main"
```

## URI overview

| URI | Purpose |
| --- | --- |
| `awam://root/` | Backend directory |
| `awam://local/<path>` | Local filesystem path |
| `awam://local/unc/<server>/<share>` | UNC path (`\\server\share`) |
| `awam://search/everything?q=<term>` | Everything search results as a virtual directory |
| `awam://rclone/<remote>/...` | Any configured rclone remote, without code changes |
| `awam://knowledge/<graph>/...` | Knowledge base; `_flat` gives a flat page view |
| `awam://downloads/qb/` | qBittorrent tasks (WebUI must be enabled) |
| `awam://prowlarr/search?q=<term>` | Prowlarr search |
| `awam://smb/` | Mapped shares plus `AWAM_SMB_ROOTS` |
| `awam://places/recycle` | Recycle bin |
| `awam://places/recent` | Recently used files |
| `awam://places/downloads` | User and Public download folders |
| `awam://browser/` | Browser bookmarks (Chrome + Edge first); `resolve` → `open_url` |
| `awam://hf/cache/` | Local Hugging Face hub cache |
| `awam://wsl/<distro>/` | List distributions (stopped ones are not started) |
| `awam://docker/` | Volume metadata while the engine is running |
| `awam://kopia/` | Snapshots when the CLI and a repo are available |

See [docs/uri-spec.md](docs/uri-spec.md) for the full specification.

## Configuration

Configuration lives in environment variables. A `.env` file at the project root is loaded at startup and is gitignored; variables already present in the environment take precedence over the file.

API keys and other secrets belong in `.env` (for example `AWAM_PROWLARR_API_KEY`) and must never be committed.

Executable paths for tool-backed backends can be overridden (in `.env` or the environment):

| Tool | Variable | Default |
| --- | --- | --- |
| kopia | `AWAM_KOPIA_EXE` | `kopia` |
| Everything | `AWAM_ES_EXE` | `es.exe` |
| rclone | `AWAM_RCLONE_EXE` | `rclone` |
| Docker | `AWAM_DOCKER_EXE` | `docker` |
| WSL | `AWAM_WSL_EXE` | `wsl.exe` |
| PowerShell | `AWAM_POWERSHELL_EXE` | `powershell.exe` |
| Directory Opus | `AWAM_DOPUSRT` | platform default |

A bare command name is resolved through `PATH`; an absolute path must exist, otherwise the backend reports `configured executable not found: ...` instead of silently falling back.

## MCP tools

`res_backends`, `res_list`, `res_stat`, `res_read`, `res_search`, `res_resolve`, `res_open_in_dopus`, `res_push_to_downloads`.

## License

MIT. See [LICENSE](LICENSE).
