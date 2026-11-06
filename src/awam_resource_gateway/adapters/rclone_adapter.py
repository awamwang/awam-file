from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import (
    BackendInfo,
    DirListing,
    ReadResult,
    ResolveResult,
    ResourceEntry,
    StatResult,
)
from awam_resource_gateway.uri import AwamUri


class RcloneAdapter(Adapter):
    backend_id = "rclone"
    name = "rclone"
    description = "Cloud / SFTP / WebDAV via rclone CLI (no mount)"

    def _rclone(self) -> str | None:
        configured = self.config.rclone_exe
        return shutil.which(configured) or (configured if configured else None)

    def _run(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        exe = self._rclone()
        if not exe:
            raise FileNotFoundError("rclone not found")
        return subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    def health(self) -> BackendInfo:
        exe = self._rclone()
        if not exe:
            return BackendInfo(
                id=self.backend_id,
                name=self.name,
                description=self.description,
                healthy=False,
                capabilities=["list", "stat"],
                detail="rclone not found on PATH",
            )
        try:
            result = self._run(["listremotes"], timeout=15)
            remotes = [line.strip().rstrip(":") for line in result.stdout.splitlines() if line.strip()]
            detail = f"{len(remotes)} remote(s)" if remotes else "No remotes configured (rclone config)"
            return BackendInfo(
                id=self.backend_id,
                name=self.name,
                description=self.description,
                healthy=result.returncode == 0,
                capabilities=["list", "stat", "read", "resolve"],
                detail=detail,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return BackendInfo(
                id=self.backend_id,
                name=self.name,
                description=self.description,
                healthy=False,
                capabilities=["list", "stat"],
                detail=str(exc),
            )

    def _list_remotes(self) -> list[str]:
        result = self._run(["listremotes"], timeout=15)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "rclone listremotes failed")
        return [line.strip().rstrip(":") for line in result.stdout.splitlines() if line.strip()]

    def _remote_spec(self, uri: AwamUri) -> str | None:
        """Convert awam://rclone/name/path → name:path"""
        if not uri.path:
            return None
        parts = uri.path.split("/", 1)
        remote = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        return f"{remote}:{rest}"

    def list(self, uri: AwamUri) -> DirListing:
        try:
            if not self._rclone():
                return DirListing(
                    uri=uri.to_string(),
                    entries=[],
                    backend=self.backend_id,
                    error="rclone not found on PATH",
                )
            if not uri.path:
                remotes = self._list_remotes()
                if not remotes:
                    return DirListing(
                        uri=uri.to_string(),
                        entries=[],
                        backend=self.backend_id,
                        error="No rclone remotes. Run: rclone config",
                    )
                entries = [
                    ResourceEntry(
                        name=name,
                        uri=uri.child(name).to_string(),
                        is_dir=True,
                        is_file=False,
                    )
                    for name in remotes
                ]
                return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

            spec = self._remote_spec(uri)
            assert spec is not None
            result = self._run(["lsjson", "--dirs-only=false", spec], timeout=90)
            if result.returncode != 0:
                return DirListing(
                    uri=uri.to_string(),
                    entries=[],
                    backend=self.backend_id,
                    error=(result.stderr or result.stdout or "rclone lsjson failed").strip(),
                )
            items = json.loads(result.stdout or "[]")
            entries: list[ResourceEntry] = []
            for item in items:
                name = item.get("Name") or item.get("Path") or ""
                if not name:
                    continue
                # Prefer basename
                name = str(name).replace("\\", "/").rstrip("/").split("/")[-1]
                is_dir = bool(item.get("IsDir"))
                size = int(item.get("Size") or 0)
                mtime = 0.0
                mod = item.get("ModTime")
                if mod:
                    try:
                        mtime = datetime.fromisoformat(str(mod).replace("Z", "+00:00")).timestamp()
                    except ValueError:
                        mtime = 0.0
                entries.append(
                    ResourceEntry(
                        name=name,
                        uri=uri.child(name).to_string(),
                        is_dir=is_dir,
                        is_file=not is_dir,
                        size=0 if is_dir else size,
                        modified_time=mtime,
                        mime=item.get("MimeType"),
                        extra={"rclone": spec},
                    ),
                )
            entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
            return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, RuntimeError) as exc:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=str(exc),
            )

    def stat(self, uri: AwamUri) -> StatResult:
        if not uri.path:
            return StatResult(
                entry=ResourceEntry(
                    name="rclone",
                    uri=uri.to_string(),
                    is_dir=True,
                    is_file=False,
                ),
            )
        parent = uri.parent()
        if parent is None:
            parent = AwamUri(backend="rclone", path="", query={})
        listing = self.list(parent)
        name = uri.path.rsplit("/", 1)[-1]
        for entry in listing.entries:
            if entry.name == name:
                return StatResult(entry=entry)
        # Might be a directory — try listing it
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
        return StatResult(entry=None, error=self_listing.error or "Not found")

    def read(self, uri: AwamUri, max_bytes: int | None = None) -> ReadResult:
        spec = self._remote_spec(uri)
        if not spec or spec.endswith(":"):
            return ReadResult(uri=uri.to_string(), error="Not a file")
        exe = self._rclone()
        if not exe:
            return ReadResult(uri=uri.to_string(), error="rclone not found on PATH")
        limit = max_bytes or self.config.read_max_bytes
        try:
            proc = subprocess.Popen(
                [exe, "cat", spec],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            return ReadResult(uri=uri.to_string(), error=str(exc))
        assert proc.stdout is not None
        try:
            data = proc.stdout.read(limit + 1)
        except OSError as exc:
            proc.kill()
            proc.wait(timeout=5)
            return ReadResult(uri=uri.to_string(), error=str(exc))
        truncated = len(data) > limit
        if truncated:
            data = data[:limit]
            proc.kill()
        stderr = b""
        if proc.stderr is not None:
            try:
                stderr = proc.stderr.read()
            except OSError:
                stderr = b""
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        if proc.returncode not in (0, None) and not data:
            message = stderr.decode("utf-8", errors="replace").strip() or "rclone cat failed"
            return ReadResult(uri=uri.to_string(), error=message)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ReadResult(
                uri=uri.to_string(),
                truncated=truncated,
                error="Binary file; use rclone copyto to a local path",
            )
        return ReadResult(uri=uri.to_string(), content=text, truncated=truncated)

    def resolve(self, uri: AwamUri) -> ResolveResult:
        spec = self._remote_spec(uri)
        return ResolveResult(
            uri=uri.to_string(),
            action="rclone_path",
            action_args={"rclone_spec": spec} if spec else {},
            error="rclone paths are remote; use list/copy via rclone CLI",
        )
