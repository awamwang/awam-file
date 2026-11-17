from __future__ import annotations

import os

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import BackendInfo, DirListing, ResolveResult, ResourceEntry
from awam_resource_gateway.uri import AwamUri, local_path_to_uri
from awam_resource_gateway.win_powershell import as_rows, run_powershell_json

_LIST_SCRIPT = r"""
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$rows = @()
Get-SmbMapping -ErrorAction SilentlyContinue | ForEach-Object {
  $rows += [PSCustomObject]@{
    local = [string]$_.LocalPath
    remote = [string]$_.RemotePath
    status = [string]$_.Status
  }
}
if (-not $rows) { '[]' } else { $rows | ConvertTo-Json -Compress -Depth 3 }
"""


class SmbAdapter(Adapter):
    """Mapped SMB shares plus AWAM_SMB_ROOTS. Browsing continues on awam://local/unc/."""

    backend_id = "smb"
    name = "SMB / NAS"
    description = "Mapped Windows shares and configured UNC roots"

    def health(self) -> BackendInfo:
        if os.name != "nt":
            return self._info(False, "Windows only")
        return self._info(True, "Lists mapped shares on demand")

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
        if os.name != "nt":
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error="Windows only")
        if uri.path:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="Open the local UNC entry from awam://smb/",
            )
        entries: list[ResourceEntry] = []
        seen: set[str] = set()
        data, error = run_powershell_json(_LIST_SCRIPT, timeout=15, exe=self.config.powershell_exe)
        if error:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=error)
        for row in as_rows(data):
            remote = str(row.get("remote") or "").strip()
            local = str(row.get("local") or "").strip()
            target = remote or local
            if not target:
                continue
            key = target.replace("/", "\\").rstrip("\\").lower()
            if key in seen:
                continue
            seen.add(key)
            label = remote or local
            if local and remote:
                label = f"{local}  {remote}"
            entries.append(
                ResourceEntry(
                    name=label,
                    uri=local_path_to_uri(target),
                    is_dir=True,
                    is_file=False,
                    local_path=target,
                    extra={"status": row.get("status"), "kind": "smb-mapping"},
                ),
            )
        for root in _split_roots(self.config.smb_roots):
            key = root.replace("/", "\\").rstrip("\\").lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                ResourceEntry(
                    name=root,
                    uri=local_path_to_uri(root),
                    is_dir=True,
                    is_file=False,
                    local_path=root,
                    extra={"kind": "configured-unc"},
                ),
            )
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def resolve(self, uri: AwamUri) -> ResolveResult:
        if not uri.path:
            return ResolveResult(uri=uri.to_string(), error="SMB root has no single path")
        return ResolveResult(uri=uri.to_string(), error="Use the local UNC URI from the listing")


def _split_roots(raw: str) -> list[str]:
    parts = []
    for item in raw.replace(",", ";").split(";"):
        text = item.strip()
        if text:
            parts.append(text)
    return parts
