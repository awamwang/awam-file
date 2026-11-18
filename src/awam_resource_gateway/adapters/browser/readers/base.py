"""浏览器书签 Reader 抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BrowserProfile:
    """单个浏览器配置档案。"""

    dir_name: str
    display_name: str
    bookmarks_path: Path


class BrowserReader(ABC):
    """一种浏览器产品的书签发现与解析。

    路径约定（与 AFM 历史 URI 兼容）：
    `awam://browser/{reader.id}/{profile.dir_name}/{root_key}/{node_id}/...`
    """

    id: str
    display_name: str

    @abstractmethod
    def discover_profiles(self) -> list[BrowserProfile]:
        """返回本机可读且含 Bookmarks 文件的配置档案。"""

    @abstractmethod
    def bookmarks_doc(self, profile: BrowserProfile) -> dict[str, Any]:
        """读取并解析该档案的书签文档（产品原生结构，由适配器再映射）。"""
