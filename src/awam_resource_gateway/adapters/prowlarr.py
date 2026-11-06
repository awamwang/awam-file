from __future__ import annotations

from typing import Any

import httpx

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import (
    BackendInfo,
    DirListing,
    ResolveResult,
    ResourceEntry,
    SearchHit,
    StatResult,
)
from awam_resource_gateway.uri import AwamUri


class ProwlarrAdapter(Adapter):
    """awam://prowlarr/search?q=... — stub when service unavailable."""

    backend_id = "prowlarr"
    name = "Prowlarr"
    description = "Indexer search (requires Prowlarr running)"

    def health(self) -> BackendInfo:
        if not self.config.prowlarr_api_key:
            # Still try ping without key
            pass
        try:
            headers = {}
            if self.config.prowlarr_api_key:
                headers["X-Api-Key"] = self.config.prowlarr_api_key
            resp = httpx.get(
                f"{self.config.prowlarr_url.rstrip('/')}/api/v1/health",
                headers=headers,
                timeout=1.5,
            )
            healthy = resp.status_code < 500
            detail = f"HTTP {resp.status_code}"
            if resp.status_code == 401:
                detail = "Unauthorized — set AWAM_PROWLARR_API_KEY"
            return BackendInfo(
                id=self.backend_id,
                name=self.name,
                description=self.description,
                healthy=healthy and resp.status_code == 200,
                capabilities=["list", "search"],
                detail=detail if resp.status_code != 200 else "ok",
            )
        except httpx.HTTPError as exc:
            return BackendInfo(
                id=self.backend_id,
                name=self.name,
                description=self.description,
                healthy=False,
                capabilities=["list", "search"],
                detail=f"backend_unavailable: {exc}",
            )

    def list(self, uri: AwamUri) -> DirListing:
        if not uri.path or uri.path == "search":
            query = uri.q
            if not query:
                return DirListing(
                    uri=uri.to_string(),
                    entries=[
                        ResourceEntry(
                            name="search",
                            uri=AwamUri(backend="prowlarr", path="search", query={}).to_string(),
                            is_dir=True,
                            is_file=False,
                            extra={"hint": "Use ?q=term"},
                        ),
                    ],
                    backend=self.backend_id,
                    error=None if not uri.path else "Missing query. Use awam://prowlarr/search?q=term",
                )
            hits = self.search(query, limit=50)
            if not hits and not self.health().healthy:
                return DirListing(
                    uri=uri.to_string(),
                    entries=[],
                    backend=self.backend_id,
                    error="backend_unavailable: Prowlarr not running or API key missing",
                )
            return DirListing(
                uri=uri.to_string(),
                entries=[h.entry for h in hits],
                backend=self.backend_id,
            )
        return DirListing(
            uri=uri.to_string(),
            entries=[],
            backend=self.backend_id,
            error=f"Unknown path: {uri.path}",
        )

    def search(self, query: str, limit: int = 50) -> list[SearchHit]:
        headers: dict[str, str] = {}
        if self.config.prowlarr_api_key:
            headers["X-Api-Key"] = self.config.prowlarr_api_key
        try:
            resp = httpx.get(
                f"{self.config.prowlarr_url.rstrip('/')}/api/v1/search",
                params={"query": query},
                headers=headers,
                timeout=30.0,
            )
            if resp.status_code != 200:
                return []
            data: Any = resp.json()
            hits: list[SearchHit] = []
            for item in data[:limit] if isinstance(data, list) else []:
                title = item.get("title") or item.get("fileName") or "result"
                guid = item.get("guid") or item.get("downloadUrl") or title
                download_url = str(item.get("downloadUrl") or "")
                magnet_url = str(item.get("magnetUrl") or "")
                indexer = str(item.get("indexer") or "")
                hits.append(
                    SearchHit(
                        entry=ResourceEntry(
                            name=str(title)[:200],
                            uri=prowlarr_item_uri(
                                title=str(title),
                                download_url=download_url,
                                magnet_url=magnet_url,
                                indexer=indexer,
                            ),
                            is_dir=False,
                            is_file=True,
                            size=int(item.get("size") or 0),
                            extra={
                                "guid": guid,
                                "indexer": indexer,
                                "downloadUrl": download_url,
                                "magnetUrl": magnet_url,
                            },
                        ),
                        score=1.0,
                        source="prowlarr",
                    ),
                )
            return hits
        except httpx.HTTPError:
            return []

    def stat(self, uri: AwamUri) -> StatResult:
        if uri.path == "item":
            title = _query_one(uri, "title") or "result"
            return StatResult(
                entry=ResourceEntry(
                    name=title,
                    uri=uri.to_string(),
                    is_dir=False,
                    is_file=True,
                    extra={
                        "indexer": _query_one(uri, "indexer"),
                        "downloadUrl": _query_one(uri, "dl"),
                        "magnetUrl": _query_one(uri, "magnet"),
                    },
                ),
            )
        return StatResult(
            entry=ResourceEntry(
                name="prowlarr",
                uri=uri.to_string(),
                is_dir=True,
                is_file=False,
            ),
        )

    def resolve(self, uri: AwamUri) -> ResolveResult:
        if uri.path == "item":
            download_url = _query_one(uri, "dl")
            magnet_url = _query_one(uri, "magnet")
            if not download_url and not magnet_url:
                return ResolveResult(uri=uri.to_string(), error="Result has no magnet or download URL")
            return ResolveResult(
                uri=uri.to_string(),
                action="push_to_downloads",
                action_args={"downloadUrl": download_url, "magnetUrl": magnet_url},
                error=None,
            )
        return ResolveResult(
            uri=uri.to_string(),
            action="prowlarr_search",
            error="Search results are remote; push a result item to qBittorrent",
        )


def prowlarr_item_uri(*, title: str, download_url: str, magnet_url: str, indexer: str) -> str:
    query: dict[str, list[str]] = {}
    if title:
        query["title"] = [title[:200]]
    if download_url:
        query["dl"] = [download_url]
    if magnet_url:
        query["magnet"] = [magnet_url]
    if indexer:
        query["indexer"] = [indexer]
    return AwamUri(backend="prowlarr", path="item", query=query).to_string()


def _query_one(uri: AwamUri, key: str) -> str:
    values = uri.query.get(key) or []
    return values[0] if values else ""
