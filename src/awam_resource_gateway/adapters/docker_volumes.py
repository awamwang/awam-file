from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.adapters.local import LocalAdapter
from awam_resource_gateway.models import BackendInfo, DirListing, ResolveResult, ResourceEntry
from awam_resource_gateway.uri import AwamUri, local_path_to_uri, parse_awam_uri


class DockerVolumesAdapter(Adapter):
    """Docker volume metadata. Does not start the engine or a helper container."""

    backend_id = "docker"
    name = "Docker volumes"
    description = "docker volume ls/inspect when the engine is already running"

    def health(self) -> BackendInfo:
        exe = self._exe()
        if not exe:
            return self._info(False, "docker not found on PATH")
        result, error = self._run(["version", "--format", "{{.Server.Version}}"], timeout=6)
        if error or result is None or result.returncode != 0:
            detail = error or (result.stderr.strip() if result else "docker engine unreachable")
            return self._info(False, _short(detail))
        version = result.stdout.strip() or "running"
        return self._info(True, f"engine {version}")

    def _info(self, healthy: bool, detail: str) -> BackendInfo:
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=healthy,
            capabilities=["list", "resolve"],
            detail=detail,
        )

    def list(self, uri: AwamUri) -> DirListing:
        exe = self._exe()
        if not exe:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error="docker not found")
        if not uri.path:
            result, error = self._run(["volume", "ls", "--format", "{{json .}}"], timeout=10)
            if error or result is None or result.returncode != 0:
                detail = error or (result.stderr.strip() if result else "docker volume ls failed")
                return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=_short(detail))
            entries: list[ResourceEntry] = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue
                name = str(item.get("Name") or "")
                if not name:
                    continue
                entries.append(
                    ResourceEntry(
                        name=name,
                        uri=uri.child(name).to_string(),
                        is_dir=True,
                        is_file=False,
                        extra={"driver": item.get("Driver"), "virtual": True},
                    ),
                )
            return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)
        name = uri.path.split("/", 1)[0]
        info, error = self._inspect(name)
        if error or info is None:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=error or "inspect failed")
        mount = str(info.get("Mountpoint") or "")
        if _is_windows_path(mount):
            listing = LocalAdapter(self.config).list(parse_awam_uri(local_path_to_uri(mount)))
            listing.backend = self.backend_id
            listing.uri = uri.to_string()
            return listing
        return DirListing(
            uri=uri.to_string(),
            entries=[
                ResourceEntry(
                    name=name,
                    uri=uri.to_string(),
                    is_dir=False,
                    is_file=True,
                    extra={"mountpoint": mount, "driver": info.get("Driver"), "virtual": True},
                ),
            ],
            backend=self.backend_id,
            error="Mountpoint is inside the Docker VM; not browsed from Windows",
        )

    def resolve(self, uri: AwamUri) -> ResolveResult:
        if not uri.path:
            return ResolveResult(uri=uri.to_string(), error="Pick a volume")
        info, error = self._inspect(uri.path.split("/", 1)[0])
        if error or info is None:
            return ResolveResult(uri=uri.to_string(), error=error or "inspect failed")
        mount = str(info.get("Mountpoint") or "")
        if _is_windows_path(mount):
            return ResolveResult(uri=uri.to_string(), local_path=mount, action="open_path")
        return ResolveResult(
            uri=uri.to_string(),
            action="docker_volume",
            action_args={"mountpoint": mount},
            error="Mountpoint is not a Windows path",
        )

    def _inspect(self, name: str) -> tuple[dict[str, Any] | None, str | None]:
        result, error = self._run(["volume", "inspect", name], timeout=10)
        if error or result is None or result.returncode != 0:
            return None, error or (result.stderr.strip() if result else "inspect failed")
        try:
            payload: Any = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return None, str(exc)
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0], None
        if isinstance(payload, dict):
            return payload, None
        return None, "empty inspect result"

    def _exe(self) -> str | None:
        configured = self.config.docker_exe
        return shutil.which(configured) or (configured if configured else None)

    def _run(
        self,
        args: list[str],
        timeout: int,
    ) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
        exe = self._exe()
        if not exe:
            return None, "docker not found"
        try:
            completed = subprocess.run(
                [exe, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, str(exc)
        return completed, None


def _is_windows_path(path: str) -> bool:
    return len(path) >= 2 and path[1] == ":"


def _short(text: str) -> str:
    return " ".join(text.split())[:300]
