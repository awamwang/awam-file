from __future__ import annotations

import argparse
import asyncio
import json
import sys

from awam_resource_gateway.config import load_config
from awam_resource_gateway.gateway import ResourceGateway


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="awam-resource-gateway")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("mcp", help="Run MCP server on stdio")
    http_p = sub.add_parser("http", help="Run localhost HTTP API for Sigma/scripts")
    http_p.add_argument("--host", default=None)
    http_p.add_argument("--port", type=int, default=None)

    list_p = sub.add_parser("list", help="CLI list")
    list_p.add_argument("uri", nargs="?", default="awam://root/")

    resolve_p = sub.add_parser("resolve", help="Resolve URI")
    resolve_p.add_argument("uri")

    search_p = sub.add_parser("search", help="Search")
    search_p.add_argument("query")
    search_p.add_argument("--backend", default=None)
    search_p.add_argument("--limit", type=int, default=50)

    dopus_p = sub.add_parser("open-dopus", help="Open resolved path in Directory Opus")
    dopus_p.add_argument("uri")

    push_p = sub.add_parser("push-to-downloads", help="Push a Prowlarr item URI to qBittorrent")
    push_p.add_argument("uri")

    sub.add_parser("backends", help="Show backends")

    args = parser.parse_args(argv)
    config = load_config()
    gw = ResourceGateway(config)

    if args.cmd == "mcp":
        from awam_resource_gateway.mcp_server import run_stdio

        asyncio.run(run_stdio())
        return

    if args.cmd == "http":
        from awam_resource_gateway.http_api import run_http

        host = args.host or config.http_host
        port = args.port or config.http_port
        run_http(host, port, gw)
        return

    if args.cmd == "list":
        print(json.dumps(gw.list(args.uri).to_dict(), ensure_ascii=False, indent=2))
        return

    if args.cmd == "resolve":
        print(json.dumps(gw.resolve(args.uri).to_dict(), ensure_ascii=False, indent=2))
        return

    if args.cmd == "search":
        print(
            json.dumps(
                {"hits": gw.search(args.query, backend=args.backend, limit=args.limit)},
                ensure_ascii=False,
                indent=2,
            ),
        )
        return

    if args.cmd == "open-dopus":
        print(json.dumps(gw.open_in_dopus(args.uri), ensure_ascii=False, indent=2))
        return

    if args.cmd == "push-to-downloads":
        print(json.dumps(gw.push_to_downloads(args.uri), ensure_ascii=False, indent=2))
        return

    if args.cmd == "backends":
        print(json.dumps([b.to_dict() for b in gw.backends()], ensure_ascii=False, indent=2))
        return

    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
