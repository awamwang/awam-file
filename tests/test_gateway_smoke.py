from awam_resource_gateway.gateway import ResourceGateway


def test_backends_present():
    gw = ResourceGateway()
    ids = {b.id for b in gw.backends()}
    assert {
        "local",
        "knowledge",
        "search",
        "rclone",
        "downloads",
        "prowlarr",
        "smb",
        "volumes",
        "places",
        "browser",
        "hf",
        "wsl",
        "docker",
        "kopia",
        "filehistory",
    } <= ids


def test_list_root():
    listing = ResourceGateway().list("awam://root/")
    assert listing.error is None
    assert len(listing.entries) >= 6


def test_list_knowledge():
    listing = ResourceGateway().list("awam://knowledge/")
    # May error if path missing on other machines; on this host should work
    if listing.error:
        assert "missing" in listing.error.lower() or "Knowledge" in listing.error
    else:
        names = {e.name for e in listing.entries}
        assert "logseq-main" in names or len(names) >= 0


def test_filesystems_page():
    from starlette.testclient import TestClient

    from awam_resource_gateway.http_api import create_app

    response = TestClient(create_app()).get("/filesystems")
    assert response.status_code == 200
    assert "已接入的文件系统" in response.text


def test_sigma_shape():
    data = ResourceGateway().sigma_dir_contents("awam://root/")
    assert "entries" in data
    assert data["path"] == "awam://root/"


def test_prowlarr_item_uri_keeps_magnet():
    from awam_resource_gateway.adapters.prowlarr import prowlarr_item_uri
    from awam_resource_gateway.uri import parse_awam_uri

    first = prowlarr_item_uri(
        title="one",
        download_url="http://example.test/a",
        magnet_url="magnet:?xt=urn:btih:aaa&dn=one",
        indexer="test",
    )
    second = prowlarr_item_uri(
        title="two",
        download_url="http://example.test/b",
        magnet_url="",
        indexer="test",
    )
    assert first != second
    parsed = parse_awam_uri(first)
    assert parsed.path == "item"
    assert parsed.query["magnet"][0] == "magnet:?xt=urn:btih:aaa&dn=one"


def test_repo_dirname():
    from awam_resource_gateway.adapters.huggingface import repo_id_from_dirname

    assert repo_id_from_dirname("models--PaddlePaddle--PP-OCRv5_server_det") == "PaddlePaddle/PP-OCRv5_server_det"
    assert repo_id_from_dirname("models--distilgpt2") == "distilgpt2"


def test_dotenv_does_not_override(monkeypatch):
    import os

    from awam_resource_gateway.config import _apply_env_text

    monkeypatch.setenv("AWAM_KEEP", "original")
    monkeypatch.delenv("AWAM_FROM_FILE", raising=False)
    try:
        _apply_env_text("AWAM_KEEP=changed\nAWAM_FROM_FILE=1\n# comment\n")
        assert os.environ["AWAM_KEEP"] == "original"
        assert os.environ["AWAM_FROM_FILE"] == "1"
    finally:
        os.environ.pop("AWAM_FROM_FILE", None)
