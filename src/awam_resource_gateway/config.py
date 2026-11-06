from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _candidate_env_files() -> list[Path]:
    here = Path(__file__).resolve()
    candidates = [here.parents[2] / ".env", Path.cwd() / ".env"]
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def load_dotenv() -> None:
    """Load KEY=VALUE pairs into os.environ. Existing variables win."""
    for path in _candidate_env_files():
        if not path.is_file():
            continue
        _apply_env_text(path.read_text(encoding="utf-8"))


def _apply_env_text(text: str) -> None:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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
    smb_roots: str = field(default_factory=lambda: _env("AWAM_SMB_ROOTS", ""))
    wsl_roots: str = field(default_factory=lambda: _env("AWAM_WSL_ROOTS", ""))
    hf_endpoint: str = field(
        default_factory=lambda: _env("HF_ENDPOINT", "https://huggingface.co"),
    )
    hf_cache: str = field(default_factory=lambda: _hf_cache_dir())
    kopia_exe: str = field(default_factory=lambda: _env("AWAM_KOPIA_EXE", "kopia"))
    docker_exe: str = field(default_factory=lambda: _env("AWAM_DOCKER_EXE", "docker"))


def _hf_cache_dir() -> str:
    explicit = os.environ.get("HUGGINGFACE_HUB_CACHE")
    if explicit:
        return explicit
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return str(Path(hf_home) / "hub")
    return str(Path.home() / ".cache" / "huggingface" / "hub")


def load_config() -> GatewayConfig:
    load_dotenv()
    return GatewayConfig()
