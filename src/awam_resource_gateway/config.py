from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
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


def resolve_executable(
    configured: str,
    fallbacks: Sequence[str | Path] = (),
) -> tuple[str | None, str | None]:
    """Locate a CLI executable described by config.

    - A path-like `configured` value must exist; if it does not, return an
      actionable error instead of silently falling back to a built-in path.
    - A bare command name is looked up on PATH, then in `fallbacks`.
    Returns (path, None) on success, (None, error) for an invalid explicit
    path, or (None, None) when the tool is simply not installed.
    """
    if not configured:
        return None, None
    path_like = (
        os.path.isabs(configured)
        or os.path.sep in configured
        or bool(os.path.altsep and os.path.altsep in configured)
    )
    if path_like:
        direct = Path(configured)
        if direct.is_file():
            return str(direct), None
        found = shutil.which(configured)
        if found:
            return found, None
        return None, f"configured executable not found: {configured} (check the matching AWAM_* env var)"
    found = shutil.which(configured)
    if found:
        return found, None
    for item in fallbacks:
        candidate = Path(item)
        if candidate.is_file():
            return str(candidate), None
    return None, None


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
    download_dir: str = field(default_factory=lambda: _download_dir())
    smb_roots: str = field(default_factory=lambda: _env("AWAM_SMB_ROOTS", ""))
    wsl_roots: str = field(default_factory=lambda: _env("AWAM_WSL_ROOTS", ""))
    hf_endpoint: str = field(
        default_factory=lambda: _env("HF_ENDPOINT", "https://huggingface.co"),
    )
    hf_cache: str = field(default_factory=lambda: _hf_cache_dir())
    kopia_exe: str = field(default_factory=lambda: _env("AWAM_KOPIA_EXE", "kopia"))
    docker_exe: str = field(default_factory=lambda: _env("AWAM_DOCKER_EXE", "docker"))
    wsl_exe: str = field(default_factory=lambda: _env("AWAM_WSL_EXE", "wsl.exe"))
    powershell_exe: str = field(
        default_factory=lambda: _env("AWAM_POWERSHELL_EXE", "powershell.exe"),
    )
    backends_ttl: float = field(
        default_factory=lambda: float(_env("AWAM_BACKENDS_TTL", "30")),
    )


def _download_dir() -> str:
    explicit = os.environ.get("AWAM_DOWNLOAD_DIR")
    if explicit:
        return explicit
    return str(Path.home() / "Downloads" / "awam-file")


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
