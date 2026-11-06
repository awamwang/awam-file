from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.models import BackendInfo, DirListing, ResolveResult, ResourceEntry
from awam_resource_gateway.uri import AwamUri, local_path_to_uri


class FileHistoryAdapter(Adapter):
    backend_id = "filehistory"
    name = "File History"
    description = "Windows File History target (read-only, when enabled)"

    def health(self) -> BackendInfo:
        config_dir = _config_dir()
        enabled = config_dir.is_dir() and any(config_dir.glob("Config*.xml"))
        detail = str(config_dir) if enabled else "Windows File History is not enabled"
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=enabled,
            capabilities=["list", "resolve"],
            detail=detail,
        )

    def list(self, uri: AwamUri) -> DirListing:
        info = self.health()
        if not info.healthy:
            return DirListing(uri=uri.to_string(), entries=[], backend=self.backend_id, error=info.detail)
        target = _target_url(_config_dir())
        if uri.path:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="Open the target path; snapshot browsing stays on the local filesystem",
            )
        if not target:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error="File History config has no TargetUrl",
            )
        return DirListing(
            uri=uri.to_string(),
            entries=[
                ResourceEntry(
                    name=target,
                    uri=local_path_to_uri(target) if not target.startswith("\\\\") else local_path_to_uri(target),
                    is_dir=True,
                    is_file=False,
                    local_path=target,
                    extra={"kind": "file-history-target"},
                ),
            ],
            backend=self.backend_id,
        )

    def resolve(self, uri: AwamUri) -> ResolveResult:
        target = _target_url(_config_dir())
        if not target:
            return ResolveResult(uri=uri.to_string(), error="File History target is not configured")
        return ResolveResult(uri=uri.to_string(), local_path=target, action="open_path")


def _config_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    return Path(local) / "Microsoft" / "Windows" / "FileHistory" / "Configuration"


def _target_url(config_dir: Path) -> str | None:
    files = sorted(config_dir.glob("Config*.xml"))
    if not files:
        return None
    try:
        tree = ElementTree.parse(files[0])
    except (ElementTree.ParseError, OSError):
        return None
    node = tree.find(".//TargetUrl")
    if node is None or not (node.text or "").strip():
        return None
    return node.text.strip()
