from __future__ import annotations

import json
import mimetypes
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
from awam_resource_gateway.uri import AwamUri


class KnowledgeAdapter(Adapter):
    backend_id = "knowledge"
    name = "Knowledge"
    description = "Graphs under G:/Knowledge/data (Logseq etc.)"

    def root(self) -> Path:
        return Path(self.config.knowledge_root)

    def health(self) -> BackendInfo:
        root = self.root()
        ok = root.is_dir()
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=ok,
            capabilities=["list", "stat", "read", "resolve", "search"],
            detail=None if ok else f"Missing knowledge root: {root}",
        )

    def _graph_dirs(self) -> list[Path]:
        root = self.root()
        if not root.is_dir():
            return []
        return sorted([p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")])

    def _resolve_fs(self, uri: AwamUri) -> Path | None:
        root = self.root()
        if not uri.path:
            return root
        parts = uri.path.split("/")
        return root.joinpath(*parts)

    def _entry_for(self, path: Path, uri: AwamUri) -> ResourceEntry:
        is_dir = path.is_dir()
        try:
            st = path.stat()
            size = 0 if is_dir else int(st.st_size)
            mtime = float(st.st_mtime)
        except OSError:
            size = 0
            mtime = 0.0
        return ResourceEntry(
            name=path.name,
            uri=uri.to_string(),
            is_dir=is_dir,
            is_file=path.is_file(),
            size=size,
            modified_time=mtime,
            mime=mimetypes.guess_type(path.name)[0] if path.is_file() else None,
            local_path=str(path),
        )

    def list(self, uri: AwamUri) -> DirListing:
        root = self.root()
        if not root.is_dir():
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Knowledge root missing: {root}",
            )

        # awam://knowledge/ → graphs + virtual flat view hooks
        if not uri.path:
            entries: list[ResourceEntry] = []
            for graph in self._graph_dirs():
                child = uri.child(graph.name)
                entries.append(self._entry_for(graph, child))
            return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

        parts = uri.path.split("/")
        graph_name = parts[0]

        # Virtual flat pages: awam://knowledge/<graph>/_flat
        if len(parts) == 2 and parts[1] == "_flat":
            return self._list_flat(uri, graph_name)

        path = self._resolve_fs(uri)
        assert path is not None
        if not path.exists():
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Not found: {path}",
            )
        if not path.is_dir():
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Not a directory: {path}",
            )

        entries = []
        # At graph root, inject _flat virtual folder
        if len(parts) == 1:
            entries.append(
                ResourceEntry(
                    name="_flat",
                    uri=uri.child("_flat").to_string(),
                    is_dir=True,
                    is_file=False,
                    extra={"virtual": True, "description": "All pages flattened"},
                ),
            )

        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError as exc:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=str(exc))

        for child in children:
            if child.name.startswith(".") and child.name not in (".git",):
                continue
            child_uri = uri.child(child.name)
            entries.append(self._entry_for(child, child_uri))
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def _list_flat(self, uri: AwamUri, graph_name: str) -> DirListing:
        graph = self.root() / graph_name
        pages_dir = graph / "pages"
        journals_dir = graph / "journals"
        index_path = graph / "index.json"
        entries: list[ResourceEntry] = []

        files: list[Path] = []
        if pages_dir.is_dir():
            files.extend(pages_dir.glob("*.md"))
        if journals_dir.is_dir():
            files.extend(journals_dir.glob("*.md"))

        # Prefer index.json ordering if present
        name_order: dict[str, int] = {}
        if index_path.is_file():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for i, item in enumerate(data):
                        if isinstance(item, str):
                            name_order[item] = i
                        elif isinstance(item, dict):
                            key = item.get("name") or item.get("title") or item.get("path")
                            if key:
                                name_order[str(key)] = i
            except (OSError, json.JSONDecodeError):
                pass

        files = sorted(
            files,
            key=lambda p: (name_order.get(p.stem, 10_000), p.name.lower()),
        )
        for f in files:
            rel = f.relative_to(graph).as_posix()
            child_uri = AwamUri(backend="knowledge", path=f"{graph_name}/{rel}", query={})
            entries.append(self._entry_for(f, child_uri))
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def stat(self, uri: AwamUri) -> StatResult:
        if not uri.path:
            return StatResult(
                entry=ResourceEntry(
                    name="knowledge",
                    uri=uri.to_string(),
                    is_dir=True,
                    is_file=False,
                    local_path=str(self.root()),
                ),
            )
        parts = uri.path.split("/")
        if len(parts) == 2 and parts[1] == "_flat":
            return StatResult(
                entry=ResourceEntry(
                    name="_flat",
                    uri=uri.to_string(),
                    is_dir=True,
                    is_file=False,
                    extra={"virtual": True},
                ),
            )
        path = self._resolve_fs(uri)
        if path is None or not path.exists():
            return StatResult(entry=None, error=f"Not found: {uri.to_string()}")
        return StatResult(entry=self._entry_for(path, uri))

    def read(self, uri: AwamUri, max_bytes: int | None = None) -> ReadResult:
        path = self._resolve_fs(uri)
        if path is None or not path.is_file():
            return ReadResult(uri=uri.to_string(), error="Not a file")
        limit = max_bytes or self.config.read_max_bytes
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
                error="Binary file; use local_path",
                truncated=truncated,
            )
        return ReadResult(
            uri=uri.to_string(),
            content=text,
            local_path=str(path),
            truncated=truncated,
        )

    def resolve(self, uri: AwamUri) -> ResolveResult:
        if uri.path and uri.path.endswith("/_flat") or uri.path.endswith("_flat"):
            parts = uri.path.split("/")
            graph = self.root() / parts[0]
            return ResolveResult(
                uri=uri.to_string(),
                local_path=str(graph),
                action="open_path",
            )
        path = self._resolve_fs(uri)
        if path is None:
            return ResolveResult(uri=uri.to_string(), error="Invalid path")
        return ResolveResult(uri=uri.to_string(), local_path=str(path), action="open_path")

    def search(self, query: str, limit: int = 100) -> list[SearchHit]:
        q = query.lower().strip()
        if not q:
            return []
        hits: list[SearchHit] = []
        for graph in self._graph_dirs():
            for sub in ("pages", "journals"):
                folder = graph / sub
                if not folder.is_dir():
                    continue
                for f in folder.glob("*.md"):
                    if q in f.name.lower() or q in f.stem.lower():
                        rel = f.relative_to(self.root()).as_posix()
                        uri = AwamUri(backend="knowledge", path=rel, query={})
                        hits.append(
                            SearchHit(
                                entry=self._entry_for(f, uri),
                                score=1.0,
                                source="knowledge",
                            ),
                        )
                        if len(hits) >= limit:
                            return hits
        return hits
