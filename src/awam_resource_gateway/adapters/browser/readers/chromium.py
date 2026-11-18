"""Chromium 系浏览器共用：User Data 下 Bookmarks JSON + Local State 档案名。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from awam_resource_gateway.adapters.browser.readers.base import BrowserProfile


ROOT_KEYS: tuple[tuple[str, str], ...] = (
    ("bookmark_bar", "Bookmarks bar"),
    ("other", "Other bookmarks"),
    ("synced", "Mobile bookmarks"),
)


def discover_chromium_profiles(user_data: Path) -> list[BrowserProfile]:
    """扫描 User Data 下 Default / Profile N，仅保留可读 Bookmarks 的档案。"""
    if not user_data.is_dir():
        return []
    names = _read_profile_display_names(user_data)
    out: list[BrowserProfile] = []
    try:
        children = list(user_data.iterdir())
    except OSError:
        return []
    for child in children:
        if not child.is_dir():
            continue
        dir_name = child.name
        if not _is_profile_dir_name(dir_name):
            continue
        bookmarks_path = child / "Bookmarks"
        if not bookmarks_path.is_file():
            continue
        try:
            with bookmarks_path.open("r", encoding="utf-8"):
                pass
        except OSError:
            continue
        display = names.get(dir_name) or dir_name
        out.append(
            BrowserProfile(
                dir_name=dir_name,
                display_name=display,
                bookmarks_path=bookmarks_path,
            ),
        )
    return out


def read_bookmarks_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise ValueError(f"Bookmarks root must be object: {path}")
    return doc


def node_has_visible_children(node: dict[str, Any]) -> bool:
    children = node.get("children")
    if not isinstance(children, list):
        return False
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("type") in ("url", "folder"):
            return True
    return False


def find_node(doc: dict[str, Any], node_path: list[str]) -> dict[str, Any] | None:
    if not node_path:
        return None
    roots = doc.get("roots")
    if not isinstance(roots, dict):
        return None
    current = roots.get(node_path[0])
    if not isinstance(current, dict):
        return None
    for node_id in node_path[1:]:
        children = current.get("children")
        if not isinstance(children, list):
            return None
        match: dict[str, Any] | None = None
        for child in children:
            if isinstance(child, dict) and _node_id_matches(child, node_id):
                match = child
                break
        if match is None:
            return None
        current = match
    return current


def node_id_str(node: dict[str, Any], fallback: str) -> str:
    value = node.get("id")
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int):
        return str(value)
    return fallback


def _is_profile_dir_name(name: str) -> bool:
    if name.lower() == "default":
        return True
    if name.startswith("Profile "):
        rest = name[len("Profile ") :]
        return bool(rest) and rest.isdigit()
    return False


def _read_profile_display_names(user_data: Path) -> dict[str, str]:
    local_state = user_data / "Local State"
    try:
        raw = local_state.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    cache = (
        doc.get("profile", {}).get("info_cache")
        if isinstance(doc, dict)
        else None
    )
    if not isinstance(cache, dict):
        return {}
    out: dict[str, str] = {}
    for dir_name, info in cache.items():
        if not isinstance(info, dict):
            continue
        name = info.get("name")
        if isinstance(name, str) and name.strip():
            out[str(dir_name)] = name.strip()
    return out


def _node_id_matches(node: dict[str, Any], needle: str) -> bool:
    value = node.get("id")
    if isinstance(value, str) and value == needle:
        return True
    if isinstance(value, int) and str(value) == needle:
        return True
    return False
