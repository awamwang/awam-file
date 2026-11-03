from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass
class GatewayConfig:
    knowledge_root: str = field(
        default_factory=lambda: _env("AWAM_KNOWLEDGE_ROOT", r"G:\Knowledge\data"),
    )
    everything_es: str = field(
        default_factory=lambda: _env("AWAM_ES_EXE", "es.exe"),
    )
    rclone_exe: str = field(
        default_factory=lambda: _env("AWAM_RCLONE_EXE", "rclone"),
    )
    qb_url: str = field(
        default_factory=lambda: _env("AWAM_QB_URL", "http://127.0.0.1:8080"),
    )
    qb_username: str = field(
        default_factory=lambda: _env("AWAM_QB_USER", "admin"),
    )
    qb_password: str = field(
        default_factory=lambda: _env("AWAM_QB_PASS", ""),
    )
    prowlarr_url: str = field(
        default_factory=lambda: _env("AWAM_PROWLARR_URL", "http://127.0.0.1:9696"),
    )
    prowlarr_api_key: str = field(
        default_factory=lambda: _env("AWAM_PROWLARR_API_KEY", ""),
    )
    dopusrt: str = field(
        default_factory=lambda: _env(
            "AWAM_DOPUSRT",
            r"C:\Program Files\GPSoftware\Directory Opus\dopusrt.exe",
        ),
    )
    http_host: str = field(
        default_factory=lambda: _env("AWAM_GATEWAY_HOST", "127.0.0.1"),
    )
    http_port: int = field(
        default_factory=lambda: int(_env("AWAM_GATEWAY_PORT", "18787")),
    )
    read_max_bytes: int = field(
        default_factory=lambda: int(_env("AWAM_READ_MAX_BYTES", str(512 * 1024))),
    )


def load_config() -> GatewayConfig:
    return GatewayConfig()
