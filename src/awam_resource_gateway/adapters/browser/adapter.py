"""`awam://browser` 适配器：聚合已注册浏览器 Reader 的收藏夹树。"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.adapters.browser.readers import (
    BrowserProfile,
    BrowserReader,
    default_readers,
    reader_by_id,
)
from awam_resource_gateway.adapters.browser.readers.chromium import (
    ROOT_KEYS,
    find_node,
    node_has_visible_children,
    node_id_str,
)
from awam_resource_gateway.models import (
    BackendInfo,
    DirListing,
    ResolveResult,
    ResourceEntry,
    StatResult,
)
from awam_resource_gateway.uri import AwamUri


class BrowserAdapter(Adapter):
    backend_id = "browser"
    name = "Browser"
    description = "Browser bookmarks (Chrome/Edge first; no history)"

    def __init__(self, config, readers: list[BrowserReader] | None = None) -> None:
        super().__init__(config)
        self._readers = list(readers) if readers is not None else default_readers()

    def health(self) -> BackendInfo:
        discovered = self._discovered_readers()
        profile_count = sum(len(r.discover_profiles()) for r in discovered)
        healthy = profile_count > 0
        if healthy:
            names = " + ".join(r.display_name for r in discovered)
            detail = f"{profile_count} profile(s) · {names}"
        else:
            detail = "No Chrome/Edge Bookmarks files found under LocalAppData"
        return BackendInfo(
            id=self.backend_id,
            name=self.name,
            description=self.description,
            healthy=healthy,
            capabilities=["list", "stat", "resolve"],
            detail=detail,
        )

    def list(self, uri: AwamUri) -> DirListing:
        parts = _split_path(uri.path)
        if not parts:
            return self._list_products(uri)
        product_id = parts[0]
        reader = reader_by_id(self._readers, product_id)
        if reader is None:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Unknown browser product: {product_id}",
            )
        if len(parts) == 1:
            return self._list_profiles(uri, reader)
        profiles = {p.dir_name: p for p in reader.discover_profiles()}
        profile = profiles.get(parts[1])
        if profile is None:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Unknown profile: {parts[1]}",
            )
        if len(parts) == 2:
            return self._list_profile_roots(uri, reader, profile)
        return self._list_folder(uri, reader, profile, parts[2:])

    def stat(self, uri: AwamUri) -> StatResult:
        parts = _split_path(uri.path)
        if len(parts) >= 3:
            reader = reader_by_id(self._readers, parts[0])
            if reader is not None:
                profiles = {p.dir_name: p for p in reader.discover_profiles()}
                profile = profiles.get(parts[1])
                if profile is not None:
                    found = self._lookup_url(reader, profile, parts[2:])
                    if found is not None:
                        name, url = found
                        return StatResult(
                            entry=_entry_url(name, uri.to_string(), url, {}),
                        )
        listing = self.list(uri)
        if listing.error is None:
            name = parts[-1] if parts else self.backend_id
            return StatResult(
                entry=ResourceEntry(
                    name=name,
                    uri=uri.to_string(),
                    is_dir=True,
                    is_file=False,
                ),
            )
        if not parts or len(parts) <= 2:
            return StatResult(
                entry=ResourceEntry(
                    name=self.backend_id,
                    uri=uri.to_string(),
                    is_dir=True,
                    is_file=False,
                ),
                error=listing.error,
            )
        return StatResult(entry=None, error=listing.error)

    def resolve(self, uri: AwamUri) -> ResolveResult:
        parts = _split_path(uri.path)
        if len(parts) < 3:
            return ResolveResult(uri=uri.to_string(), error="Not a bookmark URL node")
        reader = reader_by_id(self._readers, parts[0])
        if reader is None:
            return ResolveResult(
                uri=uri.to_string(),
                error=f"Unknown browser product: {parts[0]}",
            )
        profiles = {p.dir_name: p for p in reader.discover_profiles()}
        profile = profiles.get(parts[1])
        if profile is None:
            return ResolveResult(
                uri=uri.to_string(),
                error=f"Unknown profile: {parts[1]}",
            )
        found = self._lookup_url(reader, profile, parts[2:])
        if found is None:
            return ResolveResult(uri=uri.to_string(), error="Bookmark URL not found")
        _name, url = found
        return ResolveResult(
            uri=uri.to_string(),
            action="open_url",
            action_args={"url": url},
        )

    def _discovered_readers(self) -> list[BrowserReader]:
        return [r for r in self._readers if r.discover_profiles()]

    def _list_products(self, uri: AwamUri) -> DirListing:
        entries = [
            _entry_dir(
                reader.display_name,
                uri.child(reader.id).to_string(),
                {"product": reader.id},
            )
            for reader in self._discovered_readers()
        ]
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def _list_profiles(self, uri: AwamUri, reader: BrowserReader) -> DirListing:
        profiles = sorted(
            reader.discover_profiles(),
            key=lambda p: p.display_name.lower(),
        )
        entries = [
            _entry_dir(
                profile.display_name,
                uri.child(profile.dir_name).to_string(),
                {
                    "profileDir": profile.dir_name,
                    "bookmarksPath": str(profile.bookmarks_path),
                },
            )
            for profile in profiles
        ]
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def _list_profile_roots(
        self,
        uri: AwamUri,
        reader: BrowserReader,
        profile: BrowserProfile,
    ) -> DirListing:
        try:
            doc = reader.bookmarks_doc(profile)
        except (OSError, ValueError, TypeError) as exc:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Could not read bookmarks ({profile.bookmarks_path}): {exc}",
            )
        roots = doc.get("roots") if isinstance(doc.get("roots"), dict) else {}
        entries: list[ResourceEntry] = []
        for key, fallback_name in ROOT_KEYS:
            node = roots.get(key)
            if not isinstance(node, dict) or not node_has_visible_children(node):
                continue
            name = node.get("name") if isinstance(node.get("name"), str) and node.get("name") else fallback_name
            entries.append(
                _entry_dir(
                    str(name),
                    uri.child(key).to_string(),
                    {"rootKey": key, "product": reader.id},
                ),
            )
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def _list_folder(
        self,
        uri: AwamUri,
        reader: BrowserReader,
        profile: BrowserProfile,
        node_path: list[str],
    ) -> DirListing:
        try:
            doc = reader.bookmarks_doc(profile)
        except (OSError, ValueError, TypeError) as exc:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Could not read bookmarks ({profile.bookmarks_path}): {exc}",
            )
        node = find_node(doc, node_path)
        if node is None:
            return DirListing(
                uri=uri.to_string(),
                entries=[],
                backend=self.backend_id,
                error=f"Bookmark folder not found: {uri.to_string()}",
            )
        children = node.get("children") if isinstance(node.get("children"), list) else []
        entries: list[ResourceEntry] = []
        for child in children:
            if not isinstance(child, dict):
                continue
            typ = child.get("type") or ""
            name = child.get("name") if isinstance(child.get("name"), str) else "(untitled)"
            extra = {"product": reader.id, "profileDir": profile.dir_name}
            if typ == "folder":
                node_id = node_id_str(child, str(name))
                entries.append(_entry_dir(str(name), uri.child(node_id).to_string(), extra))
            elif typ == "url":
                url = child.get("url") if isinstance(child.get("url"), str) else ""
                if not url:
                    continue
                node_id = node_id_str(child, str(name))
                entries.append(_entry_url(str(name), uri.child(node_id).to_string(), url, extra))
        return DirListing(uri=uri.to_string(), entries=entries, backend=self.backend_id)

    def _lookup_url(
        self,
        reader: BrowserReader,
        profile: BrowserProfile,
        node_path: list[str],
    ) -> tuple[str, str] | None:
        try:
            doc = reader.bookmarks_doc(profile)
        except (OSError, ValueError, TypeError):
            return None
        node = find_node(doc, node_path)
        if node is None or node.get("type") != "url":
            return None
        url = node.get("url")
        if not isinstance(url, str) or not url:
            return None
        name = node.get("name") if isinstance(node.get("name"), str) else "(untitled)"
        return str(name), url


def _split_path(path: str) -> list[str]:
    return [unquote(part) for part in path.split("/") if part]


def _entry_dir(name: str, uri: str, extra: dict[str, Any]) -> ResourceEntry:
    return ResourceEntry(
        name=name,
        uri=uri,
        is_dir=True,
        is_file=False,
        extra=extra,
    )


def _entry_url(name: str, uri: str, url: str, extra: dict[str, Any]) -> ResourceEntry:
    payload = dict(extra)
    payload["url"] = url
    payload["kind"] = "bookmark"
    return ResourceEntry(
        name=name,
        uri=uri,
        is_dir=False,
        is_file=True,
        extra=payload,
    )
