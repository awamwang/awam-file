from __future__ import annotations

import mimetypes
import os
from pathlib import Path

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
from awam_resource_gateway.uri import AwamUri, local_path_to_uri, uri_to_local_path


class LocalAdapter(Adapter):
    backend_id = "local"
    name = "Local filesystem"
    description = "Passthrough to local / UNC paths"

    def health(self) -> BackendInfo:
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=True,
            capabilities=["list", "stat", "read", "resolve", "search"],
        )

    def _path(self, uri: AwamUri) -> Path:
        local = uri_to_local_path(uri)
        if not local:
            raise FileNotFoundError("Empty local path")
        return Path(local)

    def list(self, uri: AwamUri) -> DirListing:
        if not uri.path:
            # List drive letters on Windows
            entries: list[ResourceEntry] = []
            if os.name == "nt":
                import string

                for letter in string.ascii_uppercase:
                    root = f"{letter}:\\"
                    if os.path.exists(root):
                        entries.append(
                            ResourceEntry(
                                name=f"{letter}:",
                                uri=local_path_to_uri(f"{letter}:/"),
                                is_dir=True,
                                is_file=False,
                                local_path=root,
                            ),
                        )
            else:
                entries.append(
                    ResourceEntry(
                        name="/",
                        uri=local_path_to_uri("/"),
                        is_dir=True,
                        is_file=False,
                        local_path="/",
                    ),
                )
            return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

        try:
            path = self._path(uri)
        except FileNotFoundError as exc:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=str(exc))

        if not path.exists():
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Path not found: {path}",
            )
        if not path.is_dir():
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Not a directory: {path}",
            )

        entries = []
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError as exc:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=str(exc))

        for child in children:
            try:
                is_dir = child.is_dir()
                is_file = child.is_file()
                stat = child.stat()
                size = 0 if is_dir else int(stat.st_size)
                mtime = float(stat.st_mtime)
            except OSError:
                is_dir = False
                is_file = True
                size = 0
                mtime = 0.0
            child_uri = local_path_to_uri(str(child))
            mime = mimetypes.guess_type(child.name)[0] if is_file else None
            entries.append(
                ResourceEntry(
                    name=child.name,
                    uri=child_uri,
                    is_dir=is_dir,
                    is_file=is_file,
                    size=size,
                    modified_time=mtime,
                    mime=mime,
                    local_path=str(child),
                ),
            )
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def stat(self, uri: AwamUri) -> StatResult:
        if not uri.path:
            return StatResult(
                entry=ResourceEntry(
                    name="local",
                    uri=uri.to_string(),
                    is_dir=True,
                    is_file=False,
                ),
            )
        try:
            path = self._path(uri)
        except FileNotFoundError as exc:
            return StatResult(entry=None, error=str(exc))
        if not path.exists():
            return StatResult(entry=None, error=f"Not found: {path}")
        try:
            st = path.stat()
            is_dir = path.is_dir()
            return StatResult(
                entry=ResourceEntry(
                    name=path.name or str(path),
                    uri=uri.to_string(),
                    is_dir=is_dir,
                    is_file=path.is_file(),
                    size=0 if is_dir else int(st.st_size),
                    modified_time=float(st.st_mtime),
                    mime=mimetypes.guess_type(path.name)[0] if path.is_file() else None,
                    local_path=str(path),
                ),
            )
        except OSError as exc:
            return StatResult(entry=None, error=str(exc))

    def read(self, uri: AwamUri, max_bytes: int | None = None) -> ReadResult:
        limit = max_bytes or self.config.read_max_bytes
        try:
            path = self._path(uri)
        except FileNotFoundError as exc:
            return ReadResult(uri=uri.to_string(), error=str(exc))
        if not path.is_file():
            return ReadResult(uri=uri.to_string(), local_path=str(path), error="Not a file")
        data = path.read_bytes()
        truncated = len(data) > limit
        if truncated:
            data = data[:limit]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ReadResult(
                uri=uri.to_string(),
                local_path=str(path),
                content=None,
                truncated=truncated,
                error="Binary file; use local_path",
            )
        return ReadResult(
            uri=uri.to_string(),
            content=text,
            local_path=str(path),
            truncated=truncated,
        )

    def resolve(self, uri: AwamUri) -> ResolveResult:
        local = uri_to_local_path(uri)
        if not local:
            return ResolveResult(uri=uri.to_string(), error="Empty path")
        return ResolveResult(uri=uri.to_string(), local_path=local, action="open_path")

    def search(self, query: str, limit: int = 100) -> list[SearchHit]:
        # Local adapter does not index; Everything handles filename search.
        return []
