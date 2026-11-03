#!/usr/bin/env python3
"""Resolve an awam:// URI (or local path) and open it in Directory Opus."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awam_resource_gateway.gateway import ResourceGateway  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: open_in_dopus.py <awam-uri-or-path>", file=sys.stderr)
        return 2
    uri = sys.argv[1]
    result = ResourceGateway().open_in_dopus(uri)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
