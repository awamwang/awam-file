from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from awam_resource_gateway.gateway import ResourceGateway

_gateway = ResourceGateway()
mcp = MCPServer(
    "awam-resource-gateway",
    description="Unified awam:// resource gateway for local, knowledge, Everything, rclone, downloads",
)


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool(name="res_backends", description="List resource backends and health/capabilities")
def res_backends() -> str:
    return _dump([b.to_dict() for b in _gateway.backends()])


@mcp.tool(name="res_list", description="List directory or virtual collection for an awam:// URI or local path")
def res_list(uri: str = "awam://root/") -> str:
    return _dump(_gateway.list(uri).to_dict())


@mcp.tool(name="res_stat", description="Stat a single awam:// URI or local path")
def res_stat(uri: str) -> str:
    return _dump(_gateway.stat(uri).to_dict())


@mcp.tool(name="res_read", description="Read text content of a resource (small files)")
def res_read(uri: str, max_bytes: int = 524288) -> str:
    return _dump(_gateway.read(uri, max_bytes=max_bytes).to_dict())


@mcp.tool(
    name="res_search",
    description="Search via Everything and/or knowledge filenames (optional backend=search|knowledge|prowlarr)",
)
def res_search(query: str, backend: str | None = None, limit: int = 100) -> str:
    return _dump({"query": query, "hits": _gateway.search(query, backend=backend, limit=limit)})


@mcp.tool(name="res_resolve", description="Resolve awam:// URI to a local path and/or external action")
def res_resolve(uri: str) -> str:
    return _dump(_gateway.resolve(uri).to_dict())


@mcp.tool(
    name="res_open_in_dopus",
    description="Resolve URI to local path and open it in Directory Opus (Go)",
)
def res_open_in_dopus(uri: str) -> str:
    return _dump(_gateway.open_in_dopus(uri))


async def run_stdio() -> None:
    await mcp.run_stdio_async()
