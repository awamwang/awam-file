from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

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
from awam_resource_gateway.uri import AwamUri, local_path_to_uri

# 搜索类目录的必填查询参数，缺参时返回软空态并供 UI 回填
Q_PARAM = [QueryParam(key="q", label="Query", required=True)]


class EverythingAdapter(Adapter):
    """Exposes Everything search as awam://search/everything?q=..."""

    backend_id = "search"
    name = "Everything search"
    description = "Filename search via es.exe / Everything IPC"

    def _es_path(self) -> str | None:
        configured = self.config.everything_es
        if Path(configured).is_file():
            return configured
        found = shutil.which(configured)
        return found

    def health(self) -> BackendInfo:
        es = self._es_path()
        healthy = es is not None
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=healthy,
            capabilities=["list", "search", "resolve"],
            detail=None if healthy else "es.exe not found on PATH",
        )

    def list(self, uri: AwamUri) -> DirListing:
        # awam://search/ → backends
        if not uri.path:
            return DirListing(
                uri=uri.to_string(),
                entries=[
                    ResourceEntry(
                        name="everything",
                        uri=AwamUri(backend="search", path="everything", query={}).to_string(),
                        is_dir=True,
                        is_file=False,
                        extra={"hint": "Append ?q=term to search"},
                        required_query=Q_PARAM,
                    ),
                ],
                backend=self.backend_id,
            )

        if uri.path != "everything" and not uri.path.startswith("everything/"):
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Unknown search backend path: {uri.path}",
            )

        query = uri.q
        if not query:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=None,
                required_query=Q_PARAM,
            )

        hits = self._run_es(query, limit=200)
        if not hits:
            es = self._es_path()
            detail = None
            if es:
                try:
                    probe = subprocess.run(
                        [es, "-n", "1", query],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=10,
                        check=False,
                    )
                    err = (probe.stderr or probe.stdout or "").strip()
                    if probe.returncode != 0 and err:
                        detail = err
                except (OSError, subprocess.TimeoutExpired) as exc:
                    detail = str(exc)
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=detail or "No Everything results (is Everything.exe UI/IPC running?)",
                required_query=Q_PARAM,
            )
        entries = [h.entry for h in hits]
        return DirListing(
            uri=uri.to_string(),
            entries=entries,
            backend=self.backend_id,
            required_query=Q_PARAM,
        )

    def _run_es(self, query: str, limit: int = 100) -> list[SearchHit]:
        es = self._es_path()
        if not es:
            return []
        # -n limit, -s sort by path, export path size date
        cmd = [
            es,
            "-n",
            str(limit),
            "-size",
            "-date-modified",
            query,
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []

        if completed.returncode != 0 and not completed.stdout.strip():
            # e.g. Error 8: Everything IPC window not found
            return []

        hits: list[SearchHit] = []
        for line in completed.stdout.splitlines():
            if line.lower().startswith("error "):
                continue
            line = line.strip()
            if not line:
                continue
            # es default: path only; with -size -date-modified format varies.
            # Prefer last tab-separated path if present, else whole line.
            parts = line.split("\t")
            path_str = parts[-1] if parts else line
            # Sometimes size is first
            if len(parts) >= 2 and not Path(parts[-1]).exists() and Path(parts[0]).exists():
                path_str = parts[0]
            path = Path(path_str)
            try:
                is_dir = path.is_dir()
                is_file = path.is_file()
                size = int(path.stat().st_size) if is_file else 0
                mtime = float(path.stat().st_mtime)
            except OSError:
                is_dir = path_str.endswith(("\\", "/")) or ("." not in path.name)
                is_file = not is_dir
                size = 0
                mtime = 0.0
            entry = ResourceEntry(
                name=path.name or path_str,
                uri=local_path_to_uri(str(path)),
                is_dir=is_dir,
                is_file=is_file,
                size=size,
                modified_time=mtime,
                local_path=str(path),
                extra={"search_backend": "everything"},
            )
            hits.append(SearchHit(entry=entry, score=1.0, source="everything"))
        return hits

    def search(self, query: str, limit: int = 100) -> list[SearchHit]:
        return self._run_es(query, limit=limit)

    def stat(self, uri: AwamUri) -> StatResult:
        return StatResult(
            entry=ResourceEntry(
                name=uri.path or "search",
                uri=uri.to_string(),
                is_dir=True,
                is_file=False,
            ),
        )

    def resolve(self, uri: AwamUri) -> ResolveResult:
        return ResolveResult(
            uri=uri.to_string(),
            action="search_view",
            error="Search URI has no single local path; list entries instead",
        )
