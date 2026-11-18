"""Google Chrome 书签 Reader（Chromium Bookmarks JSON）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from awam_resource_gateway.adapters.browser.readers.base import BrowserProfile, BrowserReader
from awam_resource_gateway.adapters.browser.readers.chromium import (
    discover_chromium_profiles,
    read_bookmarks_json,
)


class ChromeReader(BrowserReader):
    id = "chrome"
    display_name = "Google Chrome"

    def __init__(self, user_data: Path | None = None) -> None:
        if user_data is not None:
            self._user_data = user_data
        else:
            local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
            self._user_data = local / "Google" / "Chrome" / "User Data"

    def discover_profiles(self) -> list[BrowserProfile]:
        return discover_chromium_profiles(self._user_data)

    def bookmarks_doc(self, profile: BrowserProfile) -> dict[str, Any]:
        return read_bookmarks_json(profile.bookmarks_path)
