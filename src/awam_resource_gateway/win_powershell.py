from __future__ import annotations

import json
import subprocess
from typing import Any


def run_powershell_json(
    script: str,
    timeout: int = 25,
    exe: str = "powershell.exe",
) -> tuple[Any, str | None]:
    """Run a PowerShell script that prints JSON. Returns (data, error)."""
    try:
        completed = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    text = _decode(completed.stdout).strip()
    err = _decode(completed.stderr).strip()
    if not text:
        if completed.returncode != 0:
            return None, err or f"powershell exit {completed.returncode}"
        return None, None
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return None, err or f"invalid json: {text[:300]}"


def as_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _decode(raw: bytes) -> str:
    if not raw:
        return ""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:80]:
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")
