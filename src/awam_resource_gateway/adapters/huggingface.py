from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import (
    BackendInfo,
    DirListing,
    ReadResult,
    ResolveResult,
    ResourceEntry,
    SearchHit,
    StatResult,
)
from awam_resource_gateway.uri import AwamUri


class HuggingFaceAdapter(Adapter):
    """Local hub cache plus remote model search via HF_ENDPOINT (mirror-aware)."""

    backend_id = "hf"
    name = "Hugging Face"
    description = "Local hub cache and model search through HF_ENDPOINT"

    def health(self) -> BackendInfo:
        cache = self._hub()
        detail = f"cache={cache} endpoint={self.config.hf_endpoint}"
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=cache.is_dir() or bool(self.config.hf_endpoint),
            capabilities=["list", "stat", "read", "search"],
            detail=detail,
        )

    def _hub(self) -> Path:
        return Path(self.config.hf_cache)

    def list(self, uri: AwamUri) -> DirListing:
        if not uri.path:
            return DirListing(
                uri=uri.to_string(),
                entries=[_virtual(uri, "cache"), _virtual(uri, "remote")],
                backend=self.backend_id,
            )
        section, _, rest = uri.path.partition("/")
        if section == "remote":
            query = uri.q or ""
            if not query:
                return DirListing(
                    uri=uri.to_string(),
                    entries=[],
                    backend=self.backend_id,
                    error="Use awam://hf/remote?q=term",
                )
            hits = self.search(query, limit=30)
            return DirListing(uri=uri.to_string(), entries=[hit.entry for hit in hits], backend=self.backend_id)
        if section != "cache":
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=f"Unknown path: {section}")
        target = self._under_cache(rest)
        if target is None:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error="Path escapes the hub cache")
        if not target.exists():
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=f"Not found: {target}")
        if target.is_file():
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error="Not a directory")
        entries: list[ResourceEntry] = []
        try:
            children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=str(exc))
        for child in children:
            rel = child.relative_to(self._hub()).as_posix()
            is_dir = child.is_dir()
            entries.append(
                ResourceEntry(
                    name=_display_name(child.name) if not rest else child.name,
                    uri=AwamUri(backend="hf", path=f"cache/{rel}", query={}).to_string(),
                    is_dir=is_dir,
                    is_file=child.is_file(),
                    local_path=str(child),
                    extra={"repo_id": repo_id_from_dirname(child.name)} if child.name.startswith("models--") else {},
                ),
            )
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def stat(self, uri: AwamUri) -> StatResult:
        if not uri.path or uri.path in {"cache", "remote"}:
            return StatResult(
                entry=ResourceEntry(name=uri.path or "hf", uri=uri.to_string(), is_dir=True, is_file=False),
            )
        section, _, rest = uri.path.partition("/")
        if section != "cache":
            return StatResult(
                entry=ResourceEntry(name=rest or "remote", uri=uri.to_string(), is_dir=False, is_file=True),
            )
        target = self._under_cache(rest)
        if target is None or not target.exists():
            return StatResult(entry=None, error="Not found")
        return StatResult(
            entry=ResourceEntry(
                name=target.name,
                uri=uri.to_string(),
                is_dir=target.is_dir(),
                is_file=target.is_file(),
                size=0 if target.is_dir() else target.stat().st_size,
                local_path=str(target),
            ),
        )

    def read(self, uri: AwamUri, max_bytes: int | None = None) -> ReadResult:
        section, _, rest = uri.path.partition("/")
        if section != "cache" or not rest:
            return ReadResult(uri=uri.to_string(), error="Only cache files can be read")
        target = self._under_cache(rest)
        if target is None:
            return ReadResult(uri=uri.to_string(), error="Path escapes the hub cache")
        if not target.is_file():
            return ReadResult(uri=uri.to_string(), local_path=str(target), error="Not a file")
        limit = max_bytes or self.config.read_max_bytes
        data = target.read_bytes()
        truncated = len(data) > limit
        if truncated:
            data = data[:limit]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ReadResult(uri=uri.to_string(), local_path=str(target), truncated=truncated, error="Binary file; use local_path")
        return ReadResult(uri=uri.to_string(), content=text, local_path=str(target), truncated=truncated)

    def search(self, query: str, limit: int = 30) -> list[SearchHit]:
        endpoint = self.config.hf_endpoint.rstrip("/")
        try:
            resp = httpx.get(
                f"{endpoint}/api/models",
                params={"search": query, "limit": min(limit, 50)},
                timeout=20.0,
            )
        except httpx.HTTPError:
            return []
        if resp.status_code != 200:
            return []
        payload: Any = resp.json()
        hits: list[SearchHit] = []
        if not isinstance(payload, list):
            return hits
        for item in payload[:limit]:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or item.get("modelId") or "")
            if not model_id:
                continue
            hits.append(
                SearchHit(
                    entry=ResourceEntry(
                        name=model_id,
                        uri=AwamUri(backend="hf", path=f"remote/{model_id}", query={"q": [query]}).to_string(),
                        is_dir=False,
                        is_file=True,
                        extra={
                            "pipeline": item.get("pipeline_tag"),
                            "downloads": item.get("downloads"),
                            "endpoint": endpoint,
                        },
                    ),
                    score=1.0,
                    source="huggingface",
                ),
            )
        return hits

    def resolve(self, uri: AwamUri) -> ResolveResult:
        section, _, rest = uri.path.partition("/")
        if section == "cache" and rest:
            target = self._under_cache(rest)
            if target is not None and target.exists():
                return ResolveResult(uri=uri.to_string(), local_path=str(target), action="open_path")
        return ResolveResult(uri=uri.to_string(), error="Remote models are metadata only; cache entries have local paths")

    def _under_cache(self, relative: str) -> Path | None:
        root = self._hub().resolve()
        candidate = (root / relative).resolve() if relative else root
        if not candidate.is_relative_to(root):
            return None
        return candidate


def repo_id_from_dirname(dirname: str) -> str | None:
    if not dirname.startswith("models--"):
        return None
    body = dirname[len("models--") :]
    if not body:
        return None
    org, sep, name = body.partition("--")
    if not sep:
        return org
    if not org or not name:
        return None
    return f"{org}/{name}"


def _display_name(dirname: str) -> str:
    repo = repo_id_from_dirname(dirname)
    return repo or dirname


def _virtual(parent: AwamUri, name: str) -> ResourceEntry:
    return ResourceEntry(
        name=name,
        uri=parent.child(name).to_string(),
        is_dir=True,
        is_file=False,
        extra={"virtual": True},
    )
