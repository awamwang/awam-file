from __future__ import annotations

import os

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import BackendInfo, DirListing, ResolveResult, ResourceEntry
from awam_resource_gateway.uri import AwamUri, local_path_to_uri
from awam_resource_gateway.win_powershell import as_rows, run_powershell_json

_DRIVE_TYPE = {
    2: "removable",
    3: "local",
    4: "network",
    5: "cdrom",
}

_SCRIPT = r"""
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$images = @()
Get-DiskImage -ErrorAction SilentlyContinue | Where-Object { $_.Attached } | ForEach-Object {
  $letter = ''
  try {
    $part = $_ | Get-Partition -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($part -and $part.DriveLetter) { $letter = [string]$part.DriveLetter }
  } catch {}
  $images += [PSCustomObject]@{
    image = [string]$_.ImagePath
    size = [int64]$_.Size
    letter = $letter
  }
}
$disks = @()
Get-CimInstance Win32_LogicalDisk -ErrorAction SilentlyContinue | ForEach-Object {
  $disks += [PSCustomObject]@{
    device = [string]$_.DeviceID
    type = [int]$_.DriveType
    provider = [string]$_.ProviderName
    label = [string]$_.VolumeName
    fs = [string]$_.FileSystem
  }
}
@{ images = $images; disks = $disks } | ConvertTo-Json -Compress -Depth 4
"""


class VolumesAdapter(Adapter):
    """Already-mounted VHD/ISO and Windows drives. Does not mount or unlock anything."""

    backend_id = "volumes"
    name = "Mounted volumes"
    description = "Attached VHD/ISO and current drive letters (no mount/unlock)"

    def health(self) -> BackendInfo:
        detail = "Discovery only. VeraCrypt/Cryptomator are not identified unless they already have a drive letter."
        if os.name != "nt":
            detail = "Windows only"
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=os.name == "nt",
            capabilities=["list", "resolve"],
            detail=detail,
        )

    def list(self, uri: AwamUri) -> DirListing:
        if os.name != "nt":
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error="Windows only")
        section = uri.path
        if not section:
            return DirListing(
                uri=uri.to_string(),
                entries=[
                    _dir("images", uri),
                    _dir("drives", uri),
                ],
                backend=self.backend_id,
            )
        if section not in ("images", "drives"):
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="Use awam://volumes/images or awam://volumes/drives",
            )
        data, error = run_powershell_json(_SCRIPT, timeout=20, exe=self.config.powershell_exe)
        if error or not isinstance(data, dict):
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=error or "No volume data",
            )
        if section == "images":
            return DirListing(uri=uri.to_string(), entries=_images(as_rows(data.get("images"))), backend=self.backend_id)
        return DirListing(uri=uri.to_string(), entries=_drives(as_rows(data.get("disks"))), backend=self.backend_id)

    def resolve(self, uri: AwamUri) -> ResolveResult:
        return ResolveResult(uri=uri.to_string(), error="Open a drive letter or image path from the listing")


def _dir(name: str, parent: AwamUri) -> ResourceEntry:
    return ResourceEntry(
        name=name,
        uri=parent.child(name).to_string(),
        is_dir=True,
        is_file=False,
        extra={"virtual": True},
    )


def _images(rows: list[dict]) -> list[ResourceEntry]:
    entries: list[ResourceEntry] = []
    for row in rows:
        image = str(row.get("image") or "").strip()
        if not image:
            continue
        letter = str(row.get("letter") or "").strip()
        name = image.replace("\\", "/").rstrip("/").split("/")[-1]
        if letter:
            name = f"{name} ({letter}:)"
        local = f"{letter}:\\" if letter else image
        entries.append(
            ResourceEntry(
                name=name,
                uri=local_path_to_uri(local),
                is_dir=bool(letter),
                is_file=not letter,
                size=int(row.get("size") or 0),
                local_path=local,
                extra={"image": image, "kind": "disk-image"},
            ),
        )
    return entries


def _drives(rows: list[dict]) -> list[ResourceEntry]:
    entries: list[ResourceEntry] = []
    for row in rows:
        device = str(row.get("device") or "").strip()
        if not device:
            continue
        kind = _DRIVE_TYPE.get(int(row.get("type") or 0), "other")
        label = str(row.get("label") or "").strip()
        provider = str(row.get("provider") or "").strip()
        name = device
        if label:
            name = f"{device} {label}"
        if provider:
            name = f"{name}  {provider}"
        root = device if device.endswith("\\") else f"{device}\\"
        entries.append(
            ResourceEntry(
                name=f"{name} [{kind}]",
                uri=local_path_to_uri(root),
                is_dir=True,
                is_file=False,
                local_path=root,
                extra={"kind": kind, "filesystem": row.get("fs"), "provider": provider},
            ),
        )
    return entries
