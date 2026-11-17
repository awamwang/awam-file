from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

_FILESYSTEMS_HTML = (Path(__file__).resolve().parent / "filesystems.html").read_text(encoding="utf-8")

from awam_resource_gateway.gateway import ResourceGateway


def _json(data: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def create_app(gateway: ResourceGateway | None = None) -> Starlette:
    gw = gateway or ResourceGateway()

    async def health(_: Request) -> JSONResponse:
        return _json({"ok": True, "service": "awam-resource-gateway"})

    async def filesystems_page(_: Request) -> HTMLResponse:
        return HTMLResponse(_FILESYSTEMS_HTML)

    async def backends(request: Request) -> JSONResponse:
        force = request.query_params.get("refresh") == "1"
        data = await asyncio.to_thread(
            lambda: [b.to_dict() for b in gw.backends(force=force)]
        )
        return _json({"backends": data})

    async def res_list(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or "awam://root/"
        sigma = request.query_params.get("sigma") == "1"
        if sigma:
            data = await asyncio.to_thread(gw.sigma_dir_contents, uri)
            return _json(data)
        data = await asyncio.to_thread(gw.list, uri)
        return _json(data.to_dict())

    async def res_stat(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or ""
        data = await asyncio.to_thread(gw.stat, uri)
        return _json(data.to_dict())

    async def res_read(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or ""
        max_bytes = request.query_params.get("max_bytes")
        mb = int(max_bytes) if max_bytes else None
        data = await asyncio.to_thread(lambda: gw.read(uri, max_bytes=mb))
        return _json(data.to_dict())

    async def res_search(request: Request) -> JSONResponse:
        q = request.query_params.get("q") or request.query_params.get("query") or ""
        backend = request.query_params.get("backend")
        limit = int(request.query_params.get("limit") or "100")
        hits = await asyncio.to_thread(
            lambda: gw.search(q, backend=backend, limit=limit)
        )
        return _json({"query": q, "hits": hits})

    async def res_resolve(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or ""
        data = await asyncio.to_thread(gw.resolve, uri)
        return _json(data.to_dict())

    async def res_download(request: Request) -> JSONResponse:
        if request.method == "POST":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                body = {}
            uri = str(body.get("uri") or request.query_params.get("uri") or "")
        else:
            uri = request.query_params.get("uri") or ""
        data = await asyncio.to_thread(gw.download, uri)
        return _json(data.to_dict())

    async def open_dopus(request: Request) -> JSONResponse:
        if request.method == "POST":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                body = {}
            uri = body.get("uri") or request.query_params.get("uri") or ""
        else:
            uri = request.query_params.get("uri") or ""
        data = await asyncio.to_thread(gw.open_in_dopus, uri)
        return _json(data)

    async def sigma_list(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or "awam://root/"
        data = await asyncio.to_thread(gw.sigma_dir_contents, uri)
        return _json(data)

    async def push_to_downloads(request: Request) -> JSONResponse:
        if request.method == "POST":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                body = {}
            uri = str(body.get("uri") or request.query_params.get("uri") or "")
        else:
            uri = request.query_params.get("uri") or ""
        data = await asyncio.to_thread(gw.push_to_downloads, uri)
        return _json(data)

    routes = [
        Route("/health", health),
        Route("/", filesystems_page),
        Route("/filesystems", filesystems_page),
        Route("/api/backends", backends),
        Route("/api/list", res_list),
        Route("/api/stat", res_stat),
        Route("/api/read", res_read),
        Route("/api/search", res_search),
        Route("/api/resolve", res_resolve),
        Route("/api/download", res_download, methods=["GET", "POST"]),
        Route("/api/open_in_dopus", open_dopus, methods=["GET", "POST"]),
        Route("/api/sigma/list", sigma_list),
        Route("/api/push_to_downloads", push_to_downloads, methods=["GET", "POST"]),
    ]
    return Starlette(routes=routes)


def run_http(host: str, port: int, gateway: ResourceGateway | None = None) -> None:
    import uvicorn

    app = create_app(gateway)
    uvicorn.run(app, host=host, port=port, log_level="info")
