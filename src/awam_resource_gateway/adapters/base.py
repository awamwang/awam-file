from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

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
from awam_resource_gateway.uri import AwamUri

if TYPE_CHECKING:
    from awam_resource_gateway.config import GatewayConfig


class Adapter(ABC):
    backend_id: str
    name: str
    description: str

    def __init__(self, config: GatewayConfig) -> None:
        self.config = config

    @abstractmethod
    def health(self) -> BackendInfo:
        ...

    @abstractmethod
    def list(self, uri: AwamUri) -> DirListing:
        ...

    def stat(self, uri: AwamUri) -> StatResult:
        listing = self.list(uri.parent() if uri.path else uri)
        if uri.path == "":
            return StatResult(
                entry=ResourceEntry(
                    name=self.backend_id,
                    uri=uri.to_string(),
                    is_dir=True,
                    is_file=False,
                ),
            )
        name = uri.path.rsplit("/", 1)[-1]
        for entry in listing.entries:
            if entry.name == name or entry.uri.rstrip("/") == uri.to_string().rstrip("/"):
                return StatResult(entry=entry)
        # Try listing self as directory
        try:
            self_listing = self.list(uri)
            if self_listing.error is None:
                return StatResult(
                    entry=ResourceEntry(
                        name=name,
                        uri=uri.to_string(),
                        is_dir=True,
                        is_file=False,
                    ),
                )
        except Exception:
            pass
        return StatResult(entry=None, error=f"Not found: {uri.to_string()}")

    def read(self, uri: AwamUri, max_bytes: int | None = None) -> ReadResult:
        return ReadResult(uri=uri.to_string(), error=f"Read not supported for {self.backend_id}")

    def search(self, query: str, limit: int = 100) -> list[SearchHit]:
        return []

    def resolve(self, uri: AwamUri) -> ResolveResult:
        return ResolveResult(uri=uri.to_string(), error=f"No local path for {uri.to_string()}")

    def download(self, uri: AwamUri, dest_dir: str) -> DownloadResult:
        """Materialize a virtual file into dest_dir. Backends that can copy bytes
        natively override this; the default falls back to read() text content."""
        from pathlib import Path

        read = self.read(uri)
        if read.error or read.content is None:
            return DownloadResult(
                uri=uri.to_string(),
                backend=self.backend_id,
                error=read.error or "No content available",
            )
        name = uri.path.rsplit("/", 1)[-1] or f"{self.backend_id}-download.txt"
        destination = Path(dest_dir)
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / name
        target.write_text(read.content, encoding=read.encoding)
        return DownloadResult(
            uri=uri.to_string(),
            local_path=str(target),
            backend=self.backend_id,
            size=target.stat().st_size,
            ok=True,
            truncated=read.truncated,
        )
