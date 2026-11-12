from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class QueryParam:
    key: str
    label: str | None = None
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"key": self.key, "required": self.required}
        if self.label is not None:
            data["label"] = self.label
        return data


@dataclass
class ResourceEntry:
    name: str
    uri: str
    is_dir: bool
    is_file: bool
    size: int = 0
    modified_time: float = 0.0  # unix seconds
    mime: str | None = None
    local_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    required_query: list[QueryParam] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("required_query", None)
        if self.required_query is not None:
            data["requiredQuery"] = [p.to_dict() for p in self.required_query]
        return data


@dataclass
class DirListing:
    uri: str
    entries: list[ResourceEntry]
    backend: str
    error: str | None = None
    required_query: list[QueryParam] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "uri": self.uri,
            "backend": self.backend,
            "error": self.error,
            "entries": [e.to_dict() for e in self.entries],
            "total_count": len(self.entries),
            "dir_count": sum(1 for e in self.entries if e.is_dir),
            "file_count": sum(1 for e in self.entries if e.is_file),
        }
        if self.required_query is not None:
            data["requiredQuery"] = [p.to_dict() for p in self.required_query]
        return data


@dataclass
class StatResult:
    entry: ResourceEntry | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry.to_dict() if self.entry else None,
            "error": self.error,
        }


@dataclass
class ReadResult:
    uri: str
    content: str | None = None
    local_path: str | None = None
    truncated: bool = False
    error: str | None = None
    encoding: str = "utf-8"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolveResult:
    uri: str
    local_path: str | None = None
    action: str | None = None
    action_args: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BackendInfo:
    id: str
    name: str
    description: str
    healthy: bool
    capabilities: list[str]
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchHit:
    entry: ResourceEntry
    score: float = 0.0
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self.entry.to_dict()
        data["score"] = self.score
        data["source"] = self.source
        return data
