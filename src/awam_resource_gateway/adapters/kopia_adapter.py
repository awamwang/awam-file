from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import BackendInfo, DirListing, ResolveResult, ResourceEntry
from awam_resource_gateway.uri import AwamUri


class KopiaAdapter(Adapter):
    """Read-only snapshot listing when the kopia CLI is installed and a repo is connected."""

    backend_id = "kopia"
    name = "Kopia"
    description = "kopia snapshot list (no mount)"

    def health(self) -> BackendInfo:
        exe = self._exe()
        if not exe:
            return self._info(False, "kopia CLI not found. Data dir may exist without the executable.")
        return self._info(True, exe)

    def _info(self, healthy: bool, detail: str) -> BackendInfo:
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=healthy,
            capabilities=["list"],
            detail=detail,
        )

    def list(self, uri: AwamUri) -> DirListing:
        exe = self._exe()
        if not exe:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="kopia CLI not found",
            )
        if uri.path:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="Snapshot contents are not mounted. Use kopia snapshot list ids only.",
            )
        try:
            result = subprocess.run(
                [exe, "snapshot", "list", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=str(exc))
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "kopia snapshot list failed").strip()
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=message[:400])
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=str(exc))
        entries: list[ResourceEntry] = []
        rows = payload if isinstance(payload, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            snap_id = str(row.get("id") or row.get("snapshot") or "")
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            host = str(source.get("host") or "")
            path = str(source.get("path") or "")
            name = snap_id or path or "snapshot"
            if host or path:
                name = f"{name} {host}:{path}".strip()
            entries.append(
                ResourceEntry(
                    name=name[:180],
                    uri=uri.child(snap_id or name).to_string(),
                    is_dir=False,
                    is_file=True,
                    extra={"id": snap_id, "path": path, "host": host},
                ),
            )
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def resolve(self, uri: AwamUri) -> ResolveResult:
        return ResolveResult(uri=uri.to_string(), error="Kopia snapshots are not mounted by the gateway")

    def _exe(self) -> str | None:
        configured = self.config.kopia_exe
        found = shutil.which(configured)
        if found:
            return found
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local) / "Programs" / "Kopia" / "kopia.exe",
            Path(r"C:\Program Files\Kopia\kopia.exe"),
            Path(r"C:\Program Files\KopiaUI\kopia.exe"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return None
