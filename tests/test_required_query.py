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
