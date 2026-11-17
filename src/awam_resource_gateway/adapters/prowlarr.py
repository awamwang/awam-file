from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import (
    BackendInfo,
    DirListing,
    QueryParam,
    ResolveResult,
    ResourceEntry,
    SearchHit,
    StatResult,
)
from awam_resource_gateway.uri import AwamUri

# 搜索类目录的必填查询参数，缺参时返回软空态并供 UI 回填
Q_PARAM = [QueryParam(key="q", label="Query", required=True)]

# 单个 .torrent 的上限：正常种子几十 KB，超过这个量级说明地址不对。
MAX_TORRENT_BYTES = 8 * 1024 * 1024
_MAX_REDIRECTS = 3
_MAGNET_PREFIX = "magnet:"


@dataclass
class ResolvedTorrent:
    """Prowlarr 下载地址的解析结果：真 magnet、.torrent 字节，或失败说明。"""

    magnet: str = ""
    data: bytes = b""
    error: str = ""


def _error_description(body: str) -> str:
    """Prowlarr / 索引器失败时常回 XML 或 HTML 错误页，抽出可读描述。"""
    match = re.search(r'description="([^"]{1,200})"', body)
    if match:
        return match.group(1).strip()
    text = re.sub(r"<[^>]+>", " ", body)
    text = " ".join(text.split())
    return text[:160] or "empty response"


def _looks_like_torrent(data: bytes) -> bool:
    """bencode 字典 + info 段才算种子，用来挡掉登录页 / 错误 XML。"""
    return data[:1] == b"d" and b"4:info" in data[:8192]


def torrent_file_name(title: str) -> str:
    stem = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", title).strip() or "prowlarr"
    if stem.lower().endswith(".torrent"):
        stem = stem[: -len(".torrent")].strip()
    return f"{stem[:120]}.torrent"


class ProwlarrAdapter(Adapter):
    """awam://prowlarr/search?q=... — stub when service unavailable."""

    backend_id = "prowlarr"
    name = "Prowlarr"
    description = "Indexer search (requires Prowlarr running)"

    def _auth_headers(self) -> dict[str, str]:
        if not self.config.prowlarr_api_key:
            return {}
        return {"X-Api-Key": self.config.prowlarr_api_key}

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
        if not uri.path:
            return DirListing(
                uri=uri.to_string(),
                entries=[
                    ResourceEntry(
                        name="search",
                        uri=AwamUri(backend="prowlarr", path="search", query={}).to_string(),
                        is_dir=True,
                        is_file=False,
                        extra={"hint": "Use ?q=term"},
                        required_query=Q_PARAM,
                    ),
                ],
                backend=self.backend_id,
            )
        if uri.path == "search":
            query = uri.q
            if not query:
                return DirListing(
                    uri=uri.to_string(),
                    entries=[],
                    backend=self.backend_id,
                    error=None,
                    required_query=Q_PARAM,
                )
            hits = self.search(query, limit=50)
            if not hits and not self.health().healthy:
                return DirListing(
                    uri=uri.to_string(),
                    entries=[],
                    backend=self.backend_id,
                    error="backend_unavailable: Prowlarr not running or API key missing",
                    required_query=Q_PARAM,
                )
            return DirListing(
                uri=uri.to_string(),
                entries=[h.entry for h in hits],
                backend=self.backend_id,
                required_query=Q_PARAM,
            )
        return DirListing(
            uri=uri.to_string(),
            entries=[],
            backend=self.backend_id,
            error=f"Unknown path: {uri.path}",
        )

    def search(self, query: str, limit: int = 50) -> list[SearchHit]:
        headers = self._auth_headers()
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
                # 多数索引器把 guid 直接存成 magnet:，比 Prowlarr 的代理地址更好用：
                # 复制/打开时不需要 API Key，也不会被 301 到 magnet 而断链。
                if str(guid).startswith(_MAGNET_PREFIX):
                    magnet_url = str(guid)
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

    def resolve_torrent(self, url: str) -> ResolvedTorrent:
        """把 Prowlarr 的 downloadUrl / magnetUrl 变成下载器能直接吃的东西。

        Prowlarr 的这两个地址都是它自己的代理端点（链接里带 apikey），行为有三类：
        - 301/302 且 Location 是 `magnet:` → 拿到真 magnet；
        - 200 + bencode → 拿到 .torrent 字节；
        - 500/429 等 → 返回 XML/HTML 错误页，浏览器里看就是「一个网页」。
        所以这里替调用方把三种情况都判掉，不要把代理地址本身交出去。
        """
        current = url.strip()
        for _ in range(_MAX_REDIRECTS + 1):
            if current.startswith(_MAGNET_PREFIX):
                return ResolvedTorrent(magnet=current)
            if not current.startswith(("http://", "https://")):
                return ResolvedTorrent(error=f"unsupported download URL: {current[:80]}")
            try:
                resp = httpx.get(
                    current,
                    headers=self._auth_headers(),
                    timeout=10.0,
                    follow_redirects=False,
                )
            except httpx.HTTPError as exc:
                return ResolvedTorrent(error=f"backend_unavailable: {exc}")
            if resp.is_redirect:
                location = (resp.headers.get("location") or "").strip()
                if not location:
                    return ResolvedTorrent(error=f"HTTP {resp.status_code} without Location")
                current = urljoin(current, location)
                continue
            if resp.status_code != 200:
                return ResolvedTorrent(error=_error_description(resp.text))
            data = resp.content
            if len(data) > MAX_TORRENT_BYTES:
                return ResolvedTorrent(error="torrent file exceeds 8 MB")
            if not _looks_like_torrent(data):
                return ResolvedTorrent(error=_error_description(resp.text))
            return ResolvedTorrent(data=data)
        return ResolvedTorrent(error="too many redirects")

    def resolve(self, uri: AwamUri) -> ResolveResult:
        if uri.path != "item":
            return ResolveResult(
                uri=uri.to_string(),
                action="prowlarr_search",
                error="Search results are remote; push a result item to qBittorrent",
            )
        title = _query_one(uri, "title") or "result"
        magnet_url = _query_one(uri, "magnet").strip()
        download_url = _query_one(uri, "dl").strip()
        if not magnet_url and not download_url:
            return ResolveResult(uri=uri.to_string(), error="Result has no magnet or download URL")
        # 真 magnet（多数索引器 search 结果里的 guid）不需要任何网络请求。
        if magnet_url.startswith(_MAGNET_PREFIX):
            return ResolveResult(
                uri=uri.to_string(),
                action="push_to_downloads",
                action_args={"magnetUrl": magnet_url, "downloadUrl": download_url},
            )
        # Prowlarr 代理地址：先试 magnetUrl（可能 301 到 magnet），再试 downloadUrl（.torrent）。
        resolved = ResolvedTorrent()
        for candidate in (magnet_url, download_url):
            if not candidate:
                continue
            resolved = self.resolve_torrent(candidate)
            if resolved.magnet or resolved.data:
                break
        if resolved.magnet:
            return ResolveResult(
                uri=uri.to_string(),
                action="push_to_downloads",
                action_args={"magnetUrl": resolved.magnet, "downloadUrl": download_url},
            )
        if resolved.data:
            return ResolveResult(
                uri=uri.to_string(),
                action="push_to_downloads",
                action_args={
                    "downloadUrl": download_url,
                    "torrentName": torrent_file_name(title),
                    "torrentB64": base64.b64encode(resolved.data).decode("ascii"),
                },
            )
        return ResolveResult(
            uri=uri.to_string(),
            error=resolved.error or "Prowlarr did not return a torrent for this result",
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
