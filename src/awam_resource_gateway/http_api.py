from __future__ import annotations

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

    async def backends(_: Request) -> JSONResponse:
        return _json({"backends": [b.to_dict() for b in gw.backends()]})

    async def res_list(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or "awam://root/"
        sigma = request.query_params.get("sigma") == "1"
        if sigma:
            return _json(gw.sigma_dir_contents(uri))
        return _json(gw.list(uri).to_dict())

    async def res_stat(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or ""
        return _json(gw.stat(uri).to_dict())

    async def res_read(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or ""
        max_bytes = request.query_params.get("max_bytes")
        mb = int(max_bytes) if max_bytes else None
        return _json(gw.read(uri, max_bytes=mb).to_dict())

    async def res_search(request: Request) -> JSONResponse:
        q = request.query_params.get("q") or request.query_params.get("query") or ""
        backend = request.query_params.get("backend")
        limit = int(request.query_params.get("limit") or "100")
        return _json({"query": q, "hits": gw.search(q, backend=backend, limit=limit)})

    async def res_resolve(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or ""
        return _json(gw.resolve(uri).to_dict())

    async def res_download(request: Request) -> JSONResponse:
        if request.method == "POST":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                body = {}
            uri = str(body.get("uri") or request.query_params.get("uri") or "")
        else:
            uri = request.query_params.get("uri") or ""
        return _json(gw.download(uri).to_dict())

    async def open_dopus(request: Request) -> JSONResponse:
        if request.method == "POST":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                body = {}
            uri = body.get("uri") or request.query_params.get("uri") or ""
        else:
            uri = request.query_params.get("uri") or ""
        return _json(gw.open_in_dopus(uri))

    async def sigma_list(request: Request) -> JSONResponse:
        uri = request.query_params.get("uri") or "awam://root/"
        return _json(gw.sigma_dir_contents(uri))

    async def push_to_downloads(request: Request) -> JSONResponse:
        if request.method == "POST":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                body = {}
            uri = str(body.get("uri") or request.query_params.get("uri") or "")
        else:
            uri = request.query_params.get("uri") or ""
        return _json(gw.push_to_downloads(uri))

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
