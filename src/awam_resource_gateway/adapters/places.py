from __future__ import annotations

import os
from pathlib import Path

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.adapters.local import LocalAdapter
from awam_resource_gateway.models import BackendInfo, DirListing, ResolveResult, ResourceEntry
from awam_resource_gateway.uri import AwamUri, local_path_to_uri, parse_awam_uri
from awam_resource_gateway.win_powershell import as_rows, run_powershell_json

_RECYCLE_SCRIPT = r"""
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$shell = New-Object -ComObject Shell.Application
$folder = $shell.NameSpace(0x0A)
$rows = @()
foreach ($item in @($folder.Items())) {
  $rows += [PSCustomObject]@{
    name = [string]$item.Name
    path = [string]$item.Path
    size = [int64]$item.Size
    original = [string]$folder.GetDetailsOf($item, 1)
    deleted = [string]$folder.GetDetailsOf($item, 2)
  }
}
if (-not $rows) { '[]' } else { $rows | ConvertTo-Json -Compress -Depth 3 }
"""

_RECENT_SCRIPT = r"""
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$sh = New-Object -ComObject WScript.Shell
$dir = Join-Path $env:APPDATA 'Microsoft\Windows\Recent'
$rows = @()
Get-ChildItem -LiteralPath $dir -Filter *.lnk -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTimeUtc -Descending |
  Select-Object -First 100 |
  ForEach-Object {
    $target = ''
    try { $target = [string]$sh.CreateShortcut($_.FullName).TargetPath } catch {}
    $rows += [PSCustomObject]@{
      name = [string]$_.BaseName
      target = $target
      lnk = [string]$_.FullName
    }
  }
if (-not $rows) { '[]' } else { $rows | ConvertTo-Json -Compress -Depth 3 }
"""

_DOWNLOADS_SCRIPT = r"""
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$shell = New-Object -ComObject Shell.Application
$user = ''
try { $user = [string]$shell.NameSpace('shell:Downloads').Self.Path } catch {}
$public = Join-Path $env:PUBLIC 'Downloads'
@{ user = $user; public = $public } | ConvertTo-Json -Compress
"""


class PlacesAdapter(Adapter):
    backend_id = "places"
    name = "Places"
    description = "Recycle Bin, Recent, and Downloads"

    def health(self) -> BackendInfo:
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=os.name == "nt",
            capabilities=["list", "resolve"],
            detail=None if os.name == "nt" else "Windows only",
        )

    def list(self, uri: AwamUri) -> DirListing:
        if os.name != "nt":
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error="Windows only")
        section = uri.path.split("/", 1)[0] if uri.path else ""
        if not section:
            return DirListing(
                uri=uri.to_string(),
                entries=[_virtual(uri, name) for name in ("recycle", "recent", "downloads")],
                backend=self.backend_id,
            )
        if section == "recycle":
            return self._recycle(uri)
        if section == "recent":
            return self._recent(uri)
        if section == "downloads":
            return self._downloads(uri)
        return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=f"Unknown place: {section}")

    def resolve(self, uri: AwamUri) -> ResolveResult:
        return ResolveResult(uri=uri.to_string(), error="Open an item; places root is virtual")

    def _recycle(self, uri: AwamUri) -> DirListing:
        data, error = run_powershell_json(_RECYCLE_SCRIPT, timeout=30, exe=self.config.powershell_exe)
        if error:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=error)
        entries: list[ResourceEntry] = []
        for row in as_rows(data):
            name = str(row.get("name") or "deleted")
            path = str(row.get("path") or "")
            original = str(row.get("original") or "")
            local = path if path and Path(path).exists() else None
            entries.append(
                ResourceEntry(
                    name=name,
                    uri=local_path_to_uri(local) if local else uri.child(name).to_string(),
                    is_dir=False,
                    is_file=True,
                    size=int(row.get("size") or 0),
                    local_path=local,
                    extra={"original": original, "deleted": row.get("deleted"), "recycle_path": path},
                ),
            )
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def _recent(self, uri: AwamUri) -> DirListing:
        data, error = run_powershell_json(_RECENT_SCRIPT, timeout=25, exe=self.config.powershell_exe)
        if error:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=error)
        rows = as_rows(data)
        if not rows:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="No .lnk shortcuts in Recent. Jump lists under AutomaticDestinations are not expanded.",
            )
        entries: list[ResourceEntry] = []
        for row in rows:
            target = str(row.get("target") or "").strip()
            name = str(row.get("name") or target or "recent")
            local = target if target and Path(target).exists() else None
            is_dir = bool(local and Path(local).is_dir())
            entries.append(
                ResourceEntry(
                    name=name,
                    uri=local_path_to_uri(local) if local else uri.child(name).to_string(),
                    is_dir=is_dir,
                    is_file=not is_dir,
                    local_path=local,
                    extra={"lnk": row.get("lnk"), "target": target},
                ),
            )
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def _downloads(self, uri: AwamUri) -> DirListing:
        data, error = run_powershell_json(_DOWNLOADS_SCRIPT, timeout=15, exe=self.config.powershell_exe)
        user = str(Path.home() / "Downloads")
        public = str(Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Downloads")
        if isinstance(data, dict):
            user = str(data.get("user") or user)
            public = str(data.get("public") or public)
        elif error:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=error)
        entries: list[ResourceEntry] = []
        for label, folder in (("User", user), ("Public", public)):
            if not folder or not Path(folder).is_dir():
                continue
            listing = LocalAdapter(self.config).list(parse_awam_uri(local_path_to_uri(folder)))
            if listing.error:
                entries.append(
                    ResourceEntry(
                        name=label,
                        uri=local_path_to_uri(folder),
                        is_dir=True,
                        is_file=False,
                        local_path=folder,
                        extra={"error": listing.error},
                    ),
                )
                continue
            for entry in listing.entries:
                entry.name = f"{label}/{entry.name}"
                entries.append(entry)
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)


def _virtual(parent: AwamUri, name: str) -> ResourceEntry:
    return ResourceEntry(
        name=name,
        uri=parent.child(name).to_string(),
        is_dir=True,
        is_file=False,
        extra={"virtual": True},
    )
