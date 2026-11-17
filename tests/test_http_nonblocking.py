"""网关 HTTP 层非阻塞与后端健康缓存测试。

回归目标：
- 慢后端探测不能再独占事件循环（否则 /health 超时 → AFM 误判离线）。
- 后端健康结果短 TTL 缓存，刷新不再每次串行跑满所有 subprocess 探测。
"""

from __future__ import annotations

import threading
import time

import pytest
from starlette.testclient import TestClient

from awam_resource_gateway.config import GatewayConfig
from awam_resource_gateway.gateway import ResourceGateway
from awam_resource_gateway.http_api import create_app
from awam_resource_gateway.models import BackendInfo


class _SlowAdapter:
    def __init__(self, delay: float = 0.3) -> None:
        self.backend_id = "slow"
        self.delay = delay
        self.calls = 0
        self._lock = threading.Lock()

    def health(self) -> BackendInfo:
        with self._lock:
            self.calls += 1
        time.sleep(self.delay)
        return BackendInfo(
            id="slow", name="Slow", description="", healthy=True, capabilities=[]
        )


def _gw_with_slow(delay: float = 0.3, ttl: float = 30.0):
    gw = ResourceGateway(GatewayConfig(backends_ttl=ttl))
    slow = _SlowAdapter(delay)
    gw._adapters = {slow.backend_id: slow}
    return gw, slow


def test_backends_cached_until_ttl():
    gw, slow = _gw_with_slow(delay=0.01, ttl=30.0)
    gw.backends()
    t0 = time.monotonic()
    gw.backends()
    elapsed = time.monotonic() - t0
    assert slow.calls == 1
    assert elapsed < 0.005


def test_backends_force_bypasses_cache():
    gw, slow = _gw_with_slow(delay=0.0, ttl=30.0)
    gw.backends()
    gw.backends(force=True)
    assert slow.calls == 2


def test_backends_ttl_zero_always_probes():
    gw, slow = _gw_with_slow(delay=0.0, ttl=0.0)
    gw.backends()
    gw.backends()
    assert slow.calls == 2


def test_refresh_query_param_forces_rescan():
    gw, slow = _gw_with_slow(delay=0.0, ttl=30.0)
    client = TestClient(create_app(gw))
    client.get("/api/backends")
    assert slow.calls == 1
    client.get("/api/backends", params={"refresh": "1"})
    assert slow.calls == 2


def test_health_stays_fast_while_backends_probe():
    """核心回归：/api/backends 探测期间 /health 必须秒回。

    to_thread 把同步探测移出事件循环；若仍同步调用，/health 会被拖到
    至少 delay 秒（AFM 的 2s 超时就会误判离线）。
    """
    gw, slow = _gw_with_slow(delay=1.0, ttl=30.0)
    client = TestClient(create_app(gw))

    results: dict[str, float] = {}

    def probe_backends():
        t0 = time.monotonic()
        client.get("/api/backends", params={"refresh": "1"})
        results["backends"] = time.monotonic() - t0

    t = threading.Thread(target=probe_backends)
    t.start()
    time.sleep(0.05)  # 确保慢请求已进入探测阶段

    t0 = time.monotonic()
    resp = client.get("/health")
    results["health"] = time.monotonic() - t0
    t.join()

    assert resp.status_code == 200
    assert results["health"] < 0.3, (
        f"/health 被慢后端探测拖住了 {results['health']:.3f}s（事件循环被阻塞）"
    )
    assert results["backends"] >= 1.0


def test_handlers_use_to_thread():
    """源码守卫：每个阻塞型 handler 都需用 asyncio.to_thread。"""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "src/awam_resource_gateway/http_api.py"
    ).read_text(encoding="utf-8")
    assert "asyncio.to_thread" in src
    for call in ("gw.backends", "gw.list", "gw.stat", "gw.read", "gw.resolve", "gw.download"):
        assert call in src
