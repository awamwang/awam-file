from awam_resource_gateway.uri import local_path_to_uri, parse_awam_uri, uri_to_local_path


def test_parse_root():
    uri = parse_awam_uri("awam://root/")
    assert uri.backend == "root"
    assert uri.path == ""


def test_parse_local_drive():
    uri = parse_awam_uri("awam://local/G:/Knowledge/data")
    assert uri.backend == "local"
    assert uri.path.startswith("G:")
    local = uri_to_local_path(uri)
    assert local.replace("/", "\\").startswith("G:")


def test_bare_windows_path():
    uri = parse_awam_uri(r"G:\Projects")
    assert uri.backend == "local"
    assert "Projects" in uri.path


def test_search_query():
    uri = parse_awam_uri("awam://search/everything?q=readme")
    assert uri.backend == "search"
    assert uri.path == "everything"
    assert uri.q == "readme"


def test_roundtrip_local():
    u = local_path_to_uri(r"G:\Knowledge\data\logseq-main")
    parsed = parse_awam_uri(u)
    assert parsed.backend == "local"
    assert "logseq-main" in parsed.path
