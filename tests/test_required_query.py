from awam_resource_gateway.gateway import ResourceGateway
from awam_resource_gateway.models import DirListing, QueryParam, ResourceEntry


def test_dir_listing_serializes_required_query():
    listing = DirListing(
        uri="awam://hf/remote",
        entries=[],
        backend="hf",
        error=None,
        required_query=[QueryParam(key="q", label="Query", required=True)],
    )
    data = listing.to_dict()
    assert data["requiredQuery"] == [{"key": "q", "label": "Query", "required": True}]
    assert data["error"] is None


def test_resource_entry_serializes_required_query():
    entry = ResourceEntry(
        name="remote",
        uri="awam://hf/remote",
        is_dir=True,
        is_file=False,
        required_query=[QueryParam(key="q")],
    )
    data = entry.to_dict()
    assert data["requiredQuery"][0]["key"] == "q"
    assert data["requiredQuery"][0]["required"] is True


def test_everything_missing_query_is_soft():
    listing = ResourceGateway().list("awam://search/everything")
    assert listing.error is None
    assert listing.entries == []
    assert listing.required_query and listing.required_query[0].key == "q"


def test_everything_parent_declares_required_query():
    listing = ResourceGateway().list("awam://search/")
    everything = next(e for e in listing.entries if e.name == "everything")
    assert everything.required_query and everything.required_query[0].key == "q"


def test_prowlarr_search_missing_query_is_soft():
    listing = ResourceGateway().list("awam://prowlarr/search")
    assert listing.error is None
    assert listing.required_query and listing.required_query[0].key == "q"


def test_hf_remote_missing_query_is_soft():
    listing = ResourceGateway().list("awam://hf/remote")
    assert listing.error is None
    assert listing.required_query and listing.required_query[0].key == "q"


def test_hf_parent_remote_declares_required_query():
    listing = ResourceGateway().list("awam://hf/")
    remote = next(e for e in listing.entries if e.name == "remote")
    assert remote.required_query and remote.required_query[0].key == "q"
