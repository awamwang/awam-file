from __future__ import annotations

from pathlib import Path

from awam_resource_gateway.adapters.rclone_adapter import RcloneAdapter
from awam_resource_gateway.config import GatewayConfig
from awam_resource_gateway.models import DownloadResult
from awam_resource_gateway.uri import AwamUri


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _adapter_with_copy(tmp: Path) -> tuple[RcloneAdapter, list[list[str]]]:
    adapter = RcloneAdapter(GatewayConfig())
    calls: list[list[str]] = []

    def fake_rclone() -> str:
        return "rclone-stub"

    def fake_run(args: list[str], timeout: int = 60) -> _Completed:
        calls.append(list(args))
        # args = [copyto, spec, dest, ...] — materialize the target like rclone would.
        target = Path(args[2])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"remote-bytes")
        return _Completed(0)

    adapter._rclone = fake_rclone  # type: ignore[method-assign]
    adapter._run = fake_run  # type: ignore[method-assign]
    return adapter, calls


def test_resolve_marks_remote_files_downloadable():
    adapter = RcloneAdapter(GatewayConfig())
    file_uri = AwamUri(backend="rclone", path="mysftp/var/www/app.txt", query={})
    root_uri = AwamUri(backend="rclone", path="mysftp", query={})
    assert adapter.resolve(file_uri).action == "download"
    assert adapter.resolve(file_uri).action_args.get("rclone_spec") == "mysftp:var/www/app.txt"
    assert adapter.resolve(root_uri).action is None


def test_rclone_download_uses_copyto_and_returns_local_path(tmp_path: Path):
    adapter, calls = _adapter_with_copy(tmp_path)
    uri = AwamUri(backend="rclone", path="mysftp/var/www/app.txt", query={})
    result = adapter.download(uri, str(tmp_path / "out"))
    assert result.ok is True
    assert result.local_path and Path(result.local_path).is_file()
    assert result.backend == "rclone"
    assert result.action == "downloaded"
    assert Path(result.local_path).read_bytes() == b"remote-bytes"
    assert calls[0][0] == "copyto"
    assert calls[0][1] == "mysftp:var/www/app.txt"
    assert result.local_path.replace("\\", "/").endswith("mysftp/app.txt")


def test_rclone_download_rejects_directory_root(tmp_path: Path):
    adapter = RcloneAdapter(GatewayConfig())
    uri = AwamUri(backend="rclone", path="mysftp", query={})
    result = adapter.download(uri, str(tmp_path / "out"))
    assert result.ok is False
    assert result.error


def test_download_result_serializes_camel_free_contract():
    result = DownloadResult(uri="awam://rclone/x", local_path="C:/tmp/x", backend="rclone", size=3, ok=True)
    data = result.to_dict()
    assert data["local_path"] == "C:/tmp/x"
    assert data["ok"] is True
    assert data["size"] == 3
