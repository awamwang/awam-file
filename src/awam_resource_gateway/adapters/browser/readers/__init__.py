"""浏览器书签 Reader 注册表。

新增浏览器（Firefox / Brave / …）步骤：
1. 实现 `BrowserReader`（id、display_name、discover_profiles、bookmarks_doc）
2. 在本文件 `default_readers()` 中注册
3. 在 `docs/browser-bookmarks.md` 补一行说明

AFM 与其它客户端只消费 `awam://browser/...`，不必知道具体产品格式。
"""

from __future__ import annotations

from awam_resource_gateway.adapters.browser.readers.base import (
    BrowserProfile,
    BrowserReader,
)
from awam_resource_gateway.adapters.browser.readers.chrome import ChromeReader
from awam_resource_gateway.adapters.browser.readers.edge import EdgeReader

__all__ = [
    "BrowserProfile",
    "BrowserReader",
    "ChromeReader",
    "EdgeReader",
    "default_readers",
    "reader_by_id",
]


def default_readers() -> list[BrowserReader]:
    """当前已注册的书签 Reader（Chrome + Edge）。"""
    return [EdgeReader(), ChromeReader()]


def reader_by_id(readers: list[BrowserReader], product_id: str) -> BrowserReader | None:
    needle = (product_id or "").strip().lower()
    for reader in readers:
        if reader.id.lower() == needle:
            return reader
    return None
