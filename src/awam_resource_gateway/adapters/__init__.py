from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.adapters.everything_adapter import EverythingAdapter
from awam_resource_gateway.adapters.knowledge import KnowledgeAdapter
from awam_resource_gateway.adapters.local import LocalAdapter
from awam_resource_gateway.adapters.prowlarr import ProwlarrAdapter
from awam_resource_gateway.adapters.qbittorrent import QBittorrentAdapter
from awam_resource_gateway.adapters.rclone_adapter import RcloneAdapter

__all__ = [
    "Adapter",
    "LocalAdapter",
    "KnowledgeAdapter",
    "EverythingAdapter",
    "RcloneAdapter",
    "QBittorrentAdapter",
    "ProwlarrAdapter",
]
