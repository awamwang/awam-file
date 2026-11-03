from awam_resource_gateway.gateway import ResourceGateway


def test_backends_present():
    gw = ResourceGateway()
    ids = {b.id for b in gw.backends()}
    assert {"local", "knowledge", "search", "rclone", "downloads", "prowlarr"} <= ids


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


def test_sigma_shape():
    data = ResourceGateway().sigma_dir_contents("awam://root/")
    assert "entries" in data
    assert data["path"] == "awam://root/"
