from awam_resource_gateway.adapters.base import Adapter
from awam_resource_gateway.adapters.docker_volumes import DockerVolumesAdapter
from awam_resource_gateway.adapters.everything_adapter import EverythingAdapter
from awam_resource_gateway.adapters.filehistory import FileHistoryAdapter
from awam_resource_gateway.adapters.huggingface import HuggingFaceAdapter
from awam_resource_gateway.adapters.knowledge import KnowledgeAdapter
from awam_resource_gateway.adapters.kopia_adapter import KopiaAdapter
from awam_resource_gateway.adapters.local import LocalAdapter
from awam_resource_gateway.adapters.places import PlacesAdapter
from awam_resource_gateway.adapters.prowlarr import ProwlarrAdapter
from awam_resource_gateway.adapters.qbittorrent import QBittorrentAdapter
from awam_resource_gateway.adapters.rclone_adapter import RcloneAdapter
from awam_resource_gateway.adapters.smb_adapter import SmbAdapter
from awam_resource_gateway.adapters.volumes import VolumesAdapter
from awam_resource_gateway.adapters.wsl_adapter import WslAdapter

__all__ = [
    "Adapter",
    "LocalAdapter",
    "KnowledgeAdapter",
    "EverythingAdapter",
    "RcloneAdapter",
    "QBittorrentAdapter",
    "ProwlarrAdapter",
    "SmbAdapter",
    "VolumesAdapter",
    "PlacesAdapter",
    "HuggingFaceAdapter",
    "WslAdapter",
    "DockerVolumesAdapter",
    "KopiaAdapter",
    "FileHistoryAdapter",
]
