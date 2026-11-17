from awam_resource_gateway.config import GatewayConfig, resolve_executable


def test_explicit_existing_path_wins(tmp_path):
    exe = tmp_path / "tool.exe"
    exe.write_text("stub", encoding="utf-8")
    path, error = resolve_executable(str(exe), fallbacks=[tmp_path / "other.exe"])
    assert path == str(exe)
    assert error is None


def test_explicit_missing_path_reports_error_no_fallback(tmp_path):
    fallback = tmp_path / "fallback.exe"
    fallback.write_text("stub", encoding="utf-8")
    path, error = resolve_executable(
        str(tmp_path / "missing.exe"),
        fallbacks=[fallback],
    )
    assert path is None
    assert error and "not found" in error
    assert "AWAM_*" in error


def test_bare_name_uses_fallback_when_not_on_path(tmp_path):
    fallback = tmp_path / "fallback.exe"
    fallback.write_text("stub", encoding="utf-8")
    path, error = resolve_executable(
        "definitely-not-on-path-9f3a",
        fallbacks=[fallback],
    )
    assert path == str(fallback)
    assert error is None


def test_bare_name_missing_is_quiet(tmp_path):
    path, error = resolve_executable("definitely-not-on-path-9f3a")
    assert path is None
    assert error is None


def test_new_exe_env_vars(monkeypatch):
    monkeypatch.setenv("AWAM_WSL_EXE", r"D:\tools\wsl.exe")
    monkeypatch.setenv("AWAM_POWERSHELL_EXE", r"D:\tools\pwsh.exe")
    cfg = GatewayConfig()
    assert cfg.wsl_exe == r"D:\tools\wsl.exe"
    assert cfg.powershell_exe == r"D:\tools\pwsh.exe"


def test_kopia_invalid_explicit_path_surfaces_error(monkeypatch):
    from awam_resource_gateway.adapters.kopia_adapter import KopiaAdapter
    from awam_resource_gateway.uri import AwamUri

    monkeypatch.setenv("AWAM_KOPIA_EXE", r"D:\does-not-exist\kopia.exe")
    cfg = GatewayConfig()
    adapter = KopiaAdapter(cfg)
    assert "not found" in adapter.health().detail
    listing = adapter.list(AwamUri(backend="kopia", path="", query={}))
    assert listing.error and "not found" in listing.error


def test_everything_invalid_explicit_path_surfaces_error(monkeypatch):
    from awam_resource_gateway.adapters.everything_adapter import EverythingAdapter

    monkeypatch.setenv("AWAM_ES_EXE", r"D:\does-not-exist\es.exe")
    cfg = GatewayConfig()
    adapter = EverythingAdapter(cfg)
    detail = adapter.health().detail
    assert detail and "not found" in detail
