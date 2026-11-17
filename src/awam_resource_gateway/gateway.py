from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from awam_resource_gateway.adapters import (
    DockerVolumesAdapter,
    EverythingAdapter,
    FileHistoryAdapter,
    HuggingFaceAdapter,
    KnowledgeAdapter,
    KopiaAdapter,
    LocalAdapter,
    PlacesAdapter,
    ProwlarrAdapter,
    QBittorrentAdapter,
    RcloneAdapter,
    SmbAdapter,
    VolumesAdapter,
    WslAdapter,
)
from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.config import GatewayConfig, load_config
from awam_resource_gateway.models import (
    BackendInfo,
    DirListing,
    DownloadResult,
    ReadResult,
    ResolveResult,
    ResourceEntry,
    SearchHit,
    StatResult,
)
from awam_resource_gateway.uri import AwamUri, parse_awam_uri


class ResourceGateway:
    def __init__(self, config: GatewayConfig | None = None) -> None:
        self.config = config or load_config()
        adapters: list[Adapter] = [
            LocalAdapter(self.config),
            KnowledgeAdapter(self.config),
            EverythingAdapter(self.config),
            RcloneAdapter(self.config),
            QBittorrentAdapter(self.config),
            ProwlarrAdapter(self.config),
            SmbAdapter(self.config),
            VolumesAdapter(self.config),
            PlacesAdapter(self.config),
            HuggingFaceAdapter(self.config),
            WslAdapter(self.config),
            DockerVolumesAdapter(self.config),
            KopiaAdapter(self.config),
            FileHistoryAdapter(self.config),
        ]
        self._adapters: dict[str, Adapter] = {a.backend_id: a for a in adapters}

    def backends(self) -> list[BackendInfo]:
        return [a.health() for a in self._adapters.values()]

    def _adapter(self, backend: str) -> Adapter:
        if backend == "root":
            raise KeyError("root")
        try:
            return self._adapters[backend]
        except KeyError as exc:
            raise KeyError(f"Unknown backend: {backend}") from exc

    def list_root(self) -> DirListing:
        entries = [
            ResourceEntry(
                name=info.id,
                uri=AwamUri(backend=info.id, path="", query={}).to_string(),
                is_dir=True,
                is_file=False,
                extra={
                    "healthy": info.healthy,
                    "detail": info.detail,
                    "capabilities": info.capabilities,
                },
            )
            for info in self.backends()
        ]
        return DirListing(uri="awam://root/", entries=entries, backend="root")

    def list(self, uri_str: str) -> DirListing:
        uri = parse_awam_uri(uri_str)
        if uri.backend == "root":
            return self.list_root()
        try:
            return self._adapter(uri.backend).list(uri)
        except KeyError as exc:
            return DirListing(uri=uri_str, entries=[], backend=uri.backend, error=str(exc))

    def stat(self, uri_str: str) -> StatResult:
        uri = parse_awam_uri(uri_str)
        if uri.backend == "root":
            return StatResult(
                entry=ResourceEntry(
                    name="root",
                    uri="awam://root/",
                    is_dir=True,
                    is_file=False,
                ),
            )
        try:
            return self._adapter(uri.backend).stat(uri)
        except KeyError as exc:
            return StatResult(entry=None, error=str(exc))

    def read(self, uri_str: str, max_bytes: int | None = None) -> ReadResult:
        uri = parse_awam_uri(uri_str)
        if uri.backend == "root":
            return ReadResult(uri=uri_str, error="Cannot read root")
        try:
            return self._adapter(uri.backend).read(uri, max_bytes=max_bytes)
        except KeyError as exc:
            return ReadResult(uri=uri_str, error=str(exc))

    def search(self, query: str, backend: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        hits: list[SearchHit] = []
        if backend:
            if backend not in self._adapters:
                return []
            hits.extend(self._adapters[backend].search(q, limit=limit))
        else:
            # Default: Everything + knowledge
            for key in ("search", "knowledge"):
                remaining = limit - len(hits)
                if remaining <= 0:
                    break
                hits.extend(self._adapters[key].search(q, limit=remaining))
        return [h.to_dict() for h in hits[:limit]]

    def resolve(self, uri_str: str) -> ResolveResult:
        uri = parse_awam_uri(uri_str)
        if uri.backend == "root":
            return ResolveResult(uri=uri_str, error="Root has no local path")
        try:
            return self._adapter(uri.backend).resolve(uri)
        except KeyError as exc:
            return ResolveResult(uri=uri_str, error=str(exc))

    def download(self, uri_str: str) -> DownloadResult:
        """Materialize a virtual file to a local path. Local-backed entries are
        returned as-is; virtual backends copy into the configured download dir."""
        uri = parse_awam_uri(uri_str)
        if uri.backend == "root":
            return DownloadResult(uri=uri_str, error="Cannot download root")
        try:
            adapter = self._adapter(uri.backend)
        except KeyError as exc:
            return DownloadResult(uri=uri_str, error=str(exc))

        resolved = adapter.resolve(uri)
        local = resolved.local_path
        if local and Path(local).exists():
            return DownloadResult(
                uri=uri_str,
                local_path=local,
                backend=uri.backend,
                size=Path(local).stat().st_size,
                ok=True,
                action="local",
            )
        return adapter.download(uri, self.config.download_dir)

    def push_to_downloads(self, uri_str: str) -> dict[str, Any]:
        """Send a Prowlarr result magnet/URL to qBittorrent. Does not add anything else."""
        uri = parse_awam_uri(uri_str)
        if uri.backend != "prowlarr" or uri.path != "item":
            return {"ok": False, "error": "Only awam://prowlarr/item URIs can be pushed"}
        magnet = (uri.query.get("magnet") or [""])[0]
        download = (uri.query.get("dl") or [""])[0]
        target = magnet or download
        if not target:
            return {"ok": False, "error": "Result has no magnet or download URL"}
        downloads = self._adapters.get("downloads")
        add_url = getattr(downloads, "add_url", None)
        if not callable(add_url):
            return {"ok": False, "error": "downloads backend cannot add URLs"}
        result: dict[str, Any] = add_url(target)
        return result

    def open_in_dopus(self, uri_str: str) -> dict[str, Any]:
        resolved = self.resolve(uri_str)
        path = resolved.local_path
        if not path:
            return {
                "ok": False,
                "error": resolved.error or "No local path to open in Directory Opus",
                "resolve": resolved.to_dict(),
            }
        dopus = Path(self.config.dopusrt)
        if not dopus.is_file():
            return {"ok": False, "error": f"dopusrt not found: {dopus}", "local_path": path}
        try:
            subprocess.Popen(
                [str(dopus), "/cmd", f'Go "{path}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"ok": True, "local_path": path, "action": "dopus_go"}
        except OSError as exc:
            return {"ok": False, "error": str(exc), "local_path": path}

    def sigma_dir_contents(self, uri_str: str) -> dict[str, Any]:
        """Shape DirListing like Sigma DirContents for the Vue layer."""
        listing = self.list(uri_str)
        entries = []
        for e in listing.entries:
            # Prefer awam URI for virtual dirs; real local_path when available so
            # Sigma preview / open / copy keep working.
            path = e.uri
            if e.local_path and not e.extra.get("virtual"):
                path = e.local_path.replace("/", "\\") if "\\" not in e.local_path else e.local_path
            elif e.local_path and e.extra.get("virtual_link"):
                path = e.local_path
            name = e.name
            ext = None
            if e.is_file and "." in name:
                ext = name.rsplit(".", 1)[-1].lower()
            entries.append(
                {
                    "name": name,
                    "path": path,
                    "is_file": e.is_file,
                    "is_dir": e.is_dir,
                    "is_hidden": name.startswith("."),
                    "is_symlink": False,
                    "size": e.size,
                    "item_count": None,
                    "created_time": 0,
                    "modified_time": int(e.modified_time * 1000) if e.modified_time else 0,
                    "accessed_time": 0,
                    "ext": ext,
                    "mime": e.mime,
                    "awam_uri": e.uri,
                    "local_path": e.local_path,
                    "extra": e.extra,
                },
            )
        return {
            "path": uri_str,
            "entries": entries,
            "total_count": len(entries),
            "dir_count": sum(1 for e in entries if e["is_dir"]),
            "file_count": sum(1 for e in entries if e["is_file"]),
            "opened_directory_times": {
                "modified_time": 0,
                "accessed_time": 0,
                "created_time": 0,
            },
            "backend": listing.backend,
            "error": listing.error,
        }
