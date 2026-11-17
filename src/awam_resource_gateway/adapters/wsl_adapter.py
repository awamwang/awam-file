from __future__ import annotations

import os
import re
import subprocess

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.adapters.local import LocalAdapter
from awam_resource_gateway.config import resolve_executable
from awam_resource_gateway.models import BackendInfo, DirListing, ResolveResult, ResourceEntry
from awam_resource_gateway.uri import AwamUri, local_path_to_uri, parse_awam_uri


class WslAdapter(Adapter):
    """List WSL distros. Does not start a stopped distro."""

    backend_id = "wsl"
    name = "WSL"
    description = "WSL distros via \\\\wsl.localhost (no autostart)"

    def health(self) -> BackendInfo:
        distros, error = _distros(self.config.wsl_exe)
        if error:
            return self._info(False, error)
        running = sum(1 for item in distros if item[1].lower() == "running")
        return self._info(True, f"{len(distros)} distro(s), {running} running")

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
        distros, error = _distros(self.config.wsl_exe)
        if error:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=error)
        if not uri.path:
            bases = _registry_base_paths()
            entries = [_distro_entry(uri, name, state, bases.get(name)) for name, state in distros]
            entries.extend(_pins(self.config.wsl_roots, {name for name, _ in distros}))
            return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)
        distro, _, rest = uri.path.partition("/")
        state = dict(distros).get(distro)
        if state is None:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=f"Unknown distro: {distro}")
        if state.lower() != "running":
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"{distro} is {state}. Gateway will not start it.",
            )
        win_path = _wsl_path(distro, rest)
        listing = LocalAdapter(self.config).list(parse_awam_uri(local_path_to_uri(win_path)))
        listing.backend = self.backend_id
        listing.uri = uri.to_string()
        return listing

    def resolve(self, uri: AwamUri) -> ResolveResult:
        if not uri.path:
            return ResolveResult(uri=uri.to_string(), error="Pick a distro")
        distro, _, rest = uri.path.partition("/")
        distros, error = _distros(self.config.wsl_exe)
        if error:
            return ResolveResult(uri=uri.to_string(), error=error)
        state = dict(distros).get(distro)
        if state is None:
            return ResolveResult(uri=uri.to_string(), error=f"Unknown distro: {distro}")
        if state.lower() != "running":
            return ResolveResult(uri=uri.to_string(), error=f"{distro} is {state}")
        return ResolveResult(uri=uri.to_string(), local_path=_wsl_path(distro, rest), action="open_path")


def _distro_entry(parent: AwamUri, name: str, state: str, base_path: str | None) -> ResourceEntry:
    extra: dict[str, str | bool] = {"state": state, "virtual": state.lower() != "running"}
    if base_path:
        extra["base_path"] = base_path
    return ResourceEntry(
        name=f"{name} [{state}]",
        uri=parent.child(name).to_string(),
        is_dir=True,
        is_file=False,
        extra=extra,
    )


def _pins(raw: str, known: set[str]) -> list[ResourceEntry]:
    entries: list[ResourceEntry] = []
    for item in raw.split(";"):
        text = item.strip()
        if not text or ":" not in text:
            continue
        distro, _, path = text.partition(":")
        distro = distro.strip()
        path = path.strip().lstrip("/")
        if not distro or not path or distro not in known:
            continue
        win_path = _wsl_path(distro, path)
        entries.append(
            ResourceEntry(
                name=f"{distro}:{path}",
                uri=local_path_to_uri(win_path),
                is_dir=True,
                is_file=False,
                local_path=win_path,
                extra={"kind": "pinned-root", "distro": distro},
            ),
        )
    return entries


def _wsl_path(distro: str, rest: str) -> str:
    suffix = rest.replace("/", "\\").strip("\\")
    base = f"\\\\wsl.localhost\\{distro}"
    return f"{base}\\{suffix}" if suffix else base


def _registry_base_paths() -> dict[str, str]:
    """LXSS registry knows distros whose disks are outside the default package path."""
    try:
        import winreg
    except ImportError:
        return {}
    found: dict[str, str] = {}
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Lxss")
    except OSError:
        return {}
    try:
        count = winreg.QueryInfoKey(root)[0]
        for index in range(count):
            try:
                sub = winreg.OpenKey(root, winreg.EnumKey(root, index))
            except OSError:
                continue
            try:
                name, _ = winreg.QueryValueEx(sub, "DistributionName")
                base, _ = winreg.QueryValueEx(sub, "BasePath")
            except OSError:
                continue
            finally:
                winreg.CloseKey(sub)
            text = str(base)
            if text.startswith("\\\\?\\"):
                text = text[4:]
            found[str(name)] = text
    finally:
        winreg.CloseKey(root)
    return found


def _wsl_executable(configured: str) -> tuple[str | None, str | None]:
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    packaged = os.path.join(program_files, "WSL", "wsl.exe")
    return resolve_executable(configured, fallbacks=[packaged])


def _distros(configured: str) -> tuple[list[tuple[str, str]], str | None]:
    exe, exe_error = _wsl_executable(configured)
    if exe_error:
        return [], exe_error
    if not exe:
        return [], "wsl.exe not found on PATH"
    try:
        completed = subprocess.run(
            [exe, "-l", "-v"],
            capture_output=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)
    if completed.returncode != 0 and not completed.stdout:
        err = _decode(completed.stderr).strip() or f"wsl exit {completed.returncode}"
        return [], err
    text = _decode(completed.stdout)
    found: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.replace("\x00", "").strip().lstrip("*").strip()
        if not line or line.upper().startswith("NAME") or "WINDOWS SUBSYSTEM" in line.upper():
            continue
        parts = re.split(r"\s{2,}", line)
        if len(parts) < 2:
            continue
        found.append((parts[0].strip(), parts[1].strip()))
    return found, None


def _decode(raw: bytes) -> str:
    if not raw:
        return ""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:40]:
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")
