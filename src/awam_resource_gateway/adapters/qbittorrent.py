from __future__ import annotations

from typing import Any

import httpx

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import (
    BackendInfo,
    DirListing,
    ResolveResult,
    ResourceEntry,
    StatResult,
)
from awam_resource_gateway.uri import AwamUri, local_path_to_uri


class QBittorrentAdapter(Adapter):
    """awam://downloads/qb/... torrent task tree."""

    backend_id = "downloads"
    name = "Downloads (qBittorrent)"
    description = "qBittorrent WebAPI task / content browser"

    def __init__(self, config: Any) -> None:
        super().__init__(config)
        self._client: httpx.Client | None = None

    def _base(self) -> str:
        return self.config.qb_url.rstrip("/")

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self._base(), timeout=2.0)
            # login if password configured
            if self.config.qb_password or self.config.qb_username:
                try:
                    self._client.post(
                        "/api/v2/auth/login",
                        data={
                            "username": self.config.qb_username,
                            "password": self.config.qb_password,
                        },
                    )
                except httpx.HTTPError:
                    pass
        return self._client

    def health(self) -> BackendInfo:
        try:
            client = self._get_client()
            resp = client.get("/api/v2/app/version")
            if resp.status_code == 200:
                return BackendInfo(
                    id=self.backend_id,
                    name=self.name,
                    description=self.description,
                    healthy=True,
                    capabilities=["list", "stat", "resolve"],
                    detail=f"qBittorrent {resp.text.strip()}",
                )
            return BackendInfo(
                id=self.backend_id,
                name=self.name,
                description=self.description,
                healthy=False,
                capabilities=["list", "stat", "resolve"],
                detail=f"HTTP {resp.status_code}. Enable WebUI on {self._base()}",
            )
        except httpx.HTTPError as exc:
            return BackendInfo(
                id=self.backend_id,
                name=self.name,
                description=self.description,
                healthy=False,
                capabilities=["list", "stat", "resolve"],
                detail=f"Unreachable ({exc}). Enable WebUI at {self._base()}",
            )

    def list(self, uri: AwamUri) -> DirListing:
        # awam://downloads/ → qb
        if not uri.path:
            return DirListing(
                uri=uri.to_string(),
                entries=[
                    ResourceEntry(
                        name="qb",
                        uri=uri.child("qb").to_string(),
                        is_dir=True,
                        is_file=False,
                        extra={"client": "qbittorrent"},
                    ),
                ],
                backend=self.backend_id,
            )

        parts = uri.path.split("/")
        if parts[0] != "qb":
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Unknown downloads client: {parts[0]}",
            )

        try:
            client = self._get_client()
            if len(parts) == 1:
                resp = client.get("/api/v2/torrents/info")
                if resp.status_code != 200:
                    return DirListing(
                        uri=uri.to_string(),
                        entries=[],
                        backend=self.backend_id,
                        error=f"qBittorrent HTTP {resp.status_code}. Enable WebUI.",
                    )
                torrents = resp.json()
                entries = []
                for t in torrents:
                    h = t.get("hash") or ""
                    name = t.get("name") or h
                    entries.append(
                        ResourceEntry(
                            name=name,
                            uri=uri.child(h).to_string(),
                            is_dir=True,
                            is_file=False,
                            size=int(t.get("total_size") or 0),
                            local_path=t.get("save_path"),
                            extra={
                                "hash": h,
                                "state": t.get("state"),
                                "progress": t.get("progress"),
                                "save_path": t.get("save_path"),
                            },
                        ),
                    )
                return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

            torrent_hash = parts[1]
            if len(parts) == 2:
                # content files + save_path link
                resp = client.get("/api/v2/torrents/files", params={"hash": torrent_hash})
                info_resp = client.get("/api/v2/torrents/info", params={"hashes": torrent_hash})
                save_path = None
                if info_resp.status_code == 200:
                    infos = info_resp.json()
                    if infos:
                        save_path = infos[0].get("save_path")
                entries = []
                if save_path:
                    entries.append(
                        ResourceEntry(
                            name="_save_path",
                            uri=local_path_to_uri(save_path),
                            is_dir=True,
                            is_file=False,
                            local_path=save_path,
                            extra={"virtual_link": True},
                        ),
                    )
                if resp.status_code == 200:
                    for f in resp.json():
                        name = (f.get("name") or "").replace("\\", "/")
                        base = name.split("/")[-1]
                        entries.append(
                            ResourceEntry(
                                name=base or name,
                                uri=uri.child(name.replace("/", "__")).to_string(),
                                is_dir=False,
                                is_file=True,
                                size=int(f.get("size") or 0),
                                local_path=f"{save_path}\\{name}".replace("/", "\\") if save_path else None,
                                extra={"progress": f.get("progress")},
                            ),
                        )
                else:
                    return DirListing(
                        uri=uri.to_string(),
                        entries=[],
                        backend=self.backend_id,
                        error=f"files HTTP {resp.status_code}",
                    )
                return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="Use torrent hash level or open _save_path",
            )
        except httpx.HTTPError as exc:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=str(exc),
            )

    def stat(self, uri: AwamUri) -> StatResult:
        return StatResult(
            entry=ResourceEntry(
                name=uri.path.split("/")[-1] if uri.path else "downloads",
                uri=uri.to_string(),
                is_dir=True,
                is_file=False,
            ),
        )

    def resolve(self, uri: AwamUri) -> ResolveResult:
        listing = self.list(uri)
        # Prefer save_path from torrent info
        parts = uri.path.split("/") if uri.path else []
        if len(parts) >= 2 and parts[0] == "qb":
            try:
                client = self._get_client()
                info_resp = client.get("/api/v2/torrents/info", params={"hashes": parts[1]})
                if info_resp.status_code == 200 and info_resp.json():
                    save_path = info_resp.json()[0].get("save_path")
                    if save_path:
                        return ResolveResult(
                            uri=uri.to_string(),
                            local_path=save_path,
                            action="open_path",
                        )
            except httpx.HTTPError as exc:
                return ResolveResult(uri=uri.to_string(), error=str(exc))
        if listing.entries:
            for e in listing.entries:
                if e.local_path:
                    return ResolveResult(
                        uri=uri.to_string(),
                        local_path=e.local_path,
                        action="open_path",
                    )
        return ResolveResult(
            uri=uri.to_string(),
            error="No local save path (is WebUI enabled?)",
        )

    def add_url(self, url: str) -> dict[str, Any]:
        """Add a magnet or HTTP URL. Does not start a download when the call fails."""
        target = (url or "").strip()
        if not target:
            return {"ok": False, "error": "Empty download URL"}
        try:
            client = self._get_client()
            resp = client.post("/api/v2/torrents/add", data={"urls": target}, timeout=20.0)
        except httpx.HTTPError as exc:
            return {"ok": False, "error": str(exc)}
        body = (resp.text or "").strip()
        if resp.status_code == 200:
            return {"ok": True, "url": target, "detail": body or "Ok."}
        return {"ok": False, "error": f"HTTP {resp.status_code}: {body[:300]}"}
