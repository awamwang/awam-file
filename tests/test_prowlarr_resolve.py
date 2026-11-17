from __future__ import annotations

import base64

import pytest

from awam_resource_gateway.adapters import prowlarr
from awam_resource_gateway.config import GatewayConfig
from awam_resource_gateway.uri import parse_awam_uri


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b"",
        headers: dict[str, str] | None = None,
        text: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = content
        # 与 httpx 一致：响应头大小写不敏感。
        self.headers = prowlarr.httpx.Headers(headers or {})
        self.text = text if text is not None else content.decode("utf-8", "replace")

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308) and "location" in self.headers


def _adapter() -> prowlarr.ProwlarrAdapter:
    return prowlarr.ProwlarrAdapter(GatewayConfig())


def _item_uri(*, title: str = "Some.Release", magnet: str = "", dl: str = "") -> str:
    return prowlarr.prowlarr_item_uri(
        title=title, download_url=dl, magnet_url=magnet, indexer="test"
    )


def test_real_magnet_needs_no_network(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("real magnet must not trigger an HTTP request")

    monkeypatch.setattr(prowlarr.httpx, "get", boom)
    uri = parse_awam_uri(_item_uri(magnet="magnet:?xt=urn:btih:aaa&dn=one"))
    result = _adapter().resolve(uri)
    assert result.error is None
    assert result.action == "push_to_downloads"
    assert result.action_args["magnetUrl"] == "magnet:?xt=urn:btih:aaa&dn=one"


def test_redirect_to_magnet_is_followed(monkeypatch):
    monkeypatch.setattr(
        prowlarr.httpx,
        "get",
        lambda *_a, **_k: FakeResponse(status_code=301, headers={"Location": "magnet:?xt=urn:btih:bbb"}),
    )
    resolved = _adapter().resolve_torrent("http://127.0.0.1:9696/1/download?link=x")
    assert resolved.magnet == "magnet:?xt=urn:btih:bbb"
    assert resolved.error == ""


def test_torrent_bytes_are_detected(monkeypatch):
    body = b"d8:announce14:http://tracker4:infod4:name4:testee"
    monkeypatch.setattr(prowlarr.httpx, "get", lambda *_a, **_k: FakeResponse(content=body))
    resolved = _adapter().resolve_torrent("http://127.0.0.1:9696/1/download?link=x")
    assert resolved.data == body
    assert resolved.error == ""


def test_error_page_becomes_readable_error(monkeypatch):
    body = '<?xml version="1.0"?><error code="500" description="The SSL connection could not be established" />'
    monkeypatch.setattr(prowlarr.httpx, "get", lambda *_a, **_k: FakeResponse(status_code=500, content=body.encode()))
    resolved = _adapter().resolve_torrent("http://127.0.0.1:9696/1/download?link=x")
    assert resolved.data == b""
    assert "SSL connection could not be established" in resolved.error


def test_proxy_url_resolves_to_base64_torrent(monkeypatch):
    body = b"d8:announce14:http://tracker4:infod4:name4:testee"
    monkeypatch.setattr(prowlarr.httpx, "get", lambda *_a, **_k: FakeResponse(content=body))
    uri = parse_awam_uri(_item_uri(title="Some/Release: 1080p", dl="http://127.0.0.1:9696/1/download?link=x"))
    result = _adapter().resolve(uri)
    assert result.error is None
    assert "magnetUrl" not in result.action_args
    assert base64.b64decode(result.action_args["torrentB64"]) == body
    assert result.action_args["torrentName"] == "Some Release  1080p.torrent"


def test_proxy_url_failure_returns_error(monkeypatch):
    body = "<?xml version=\"1.0\"?><error code=\"429\" description=\"Indexer is disabled\" />"
    monkeypatch.setattr(prowlarr.httpx, "get", lambda *_a, **_k: FakeResponse(status_code=429, content=body.encode()))
    uri = parse_awam_uri(_item_uri(dl="http://127.0.0.1:9696/1/download?link=x"))
    result = _adapter().resolve(uri)
    assert result.action is None
    assert "Indexer is disabled" in (result.error or "")


def test_item_without_sources_reports_error():
    uri = parse_awam_uri(_item_uri())
    result = _adapter().resolve(uri)
    assert result.action is None
    assert "no magnet or download URL" in (result.error or "")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("plain", "plain.torrent"),
        ("a/b\\c:d*e?f", "a b c d e f.torrent"),
        ("already.torrent", "already.torrent"),
    ],
)
def test_torrent_file_name(title: str, expected: str):
    assert prowlarr.torrent_file_name(title) == expected
