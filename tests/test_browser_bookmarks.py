"""浏览器书签适配器：Chrome/Edge Reader 与 URI 浏览。"""

from __future__ import annotations

import json
from pathlib import Path

from awam_resource_gateway.adapters.browser.adapter import BrowserAdapter
from awam_resource_gateway.adapters.browser.readers.chrome import ChromeReader
from awam_resource_gateway.adapters.browser.readers.edge import EdgeReader
from awam_resource_gateway.config import load_config
from awam_resource_gateway.uri import parse_awam_uri

_BOOKMARKS = {
    "roots": {
        "bookmark_bar": {
            "children": [
                {
                    "id": "10",
                    "name": "Example",
                    "type": "url",
                    "url": "https://example.com/",
                },
                {
                    "id": "11",
                    "name": "Dev",
                    "type": "folder",
                    "children": [
                        {
                            "id": "12",
                            "name": "Docs",
                            "type": "url",
                            "url": "https://docs.example.com/",
                        }
                    ],
                },
            ],
            "name": "Bookmarks bar",
            "type": "folder",
        },
        "other": {"children": [], "name": "Other bookmarks", "type": "folder"},
        "synced": {"children": [], "name": "Mobile bookmarks", "type": "folder"},
    }
}


def _write_fixture(root: Path) -> tuple[Path, Path]:
    edge = root / "edge" / "User Data"
    chrome = root / "chrome" / "User Data"
    (edge / "Default").mkdir(parents=True)
    (chrome / "Profile 1").mkdir(parents=True)
    (edge / "Local State").write_text(
        json.dumps({"profile": {"info_cache": {"Default": {"name": "Edge Work"}}}}),
        encoding="utf-8",
    )
    (chrome / "Local State").write_text(
        json.dumps({"profile": {"info_cache": {"Profile 1": {"name": "Chrome Personal"}}}}),
        encoding="utf-8",
    )
    payload = json.dumps(_BOOKMARKS)
    (edge / "Default" / "Bookmarks").write_text(payload, encoding="utf-8")
    (chrome / "Profile 1" / "Bookmarks").write_text(payload, encoding="utf-8")
    (edge / "Profile 9").mkdir(parents=True)
    return edge, chrome


def test_merges_edge_and_chrome(tmp_path: Path):
    edge, chrome = _write_fixture(tmp_path)
    adapter = BrowserAdapter(
        load_config(),
        readers=[
            EdgeReader(user_data=edge),
            ChromeReader(user_data=chrome),
        ],
    )
    assert adapter.health().healthy

    root = adapter.list(parse_awam_uri("awam://browser/"))
    assert root.error is None
    assert len(root.entries) == 2
    assert {e.uri.rstrip("/") for e in root.entries} == {
        "awam://browser/edge",
        "awam://browser/chrome",
    }

    edge_profiles = adapter.list(parse_awam_uri("awam://browser/edge/"))
    assert len(edge_profiles.entries) == 1
    assert edge_profiles.entries[0].name == "Edge Work"

    bar = adapter.list(parse_awam_uri("awam://browser/edge/Default/bookmark_bar"))
    assert any(e.name == "Example" and not e.is_dir for e in bar.entries)
    assert any(e.name == "Dev" and e.is_dir for e in bar.entries)

    resolved = adapter.resolve(
        parse_awam_uri("awam://browser/edge/Default/bookmark_bar/10"),
    )
    assert resolved.action == "open_url"
    assert resolved.action_args.get("url") == "https://example.com/"

    nested = adapter.resolve(
        parse_awam_uri("awam://browser/chrome/Profile%201/bookmark_bar/11/12"),
    )
    assert nested.action == "open_url"
    assert nested.action_args.get("url") == "https://docs.example.com/"


def test_missing_user_data_unhealthy(tmp_path: Path):
    adapter = BrowserAdapter(
        load_config(),
        readers=[
            EdgeReader(user_data=tmp_path / "missing-edge"),
            ChromeReader(user_data=tmp_path / "missing-chrome"),
        ],
    )
    assert not adapter.health().healthy
    listing = adapter.list(parse_awam_uri("awam://browser/"))
    assert listing.entries == []
    assert listing.error is None
