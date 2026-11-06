from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse


SCHEME = "awam"


@dataclass(frozen=True)
class AwamUri:
    backend: str
    path: str  # no leading slash; may be empty
    query: dict[str, list[str]]

    @property
    def q(self) -> str | None:
        values = self.query.get("q") or self.query.get("query")
        if not values:
            return None
        return values[0]

    def with_path(self, path: str) -> AwamUri:
        return AwamUri(backend=self.backend, path=_normalize_inner_path(path), query=self.query)

    def child(self, name: str) -> AwamUri:
        name = name.strip("/\\")
        if not self.path:
            return self.with_path(name)
        return self.with_path(f"{self.path}/{name}")

    def parent(self) -> AwamUri | None:
        if not self.path:
            return None
        parts = self.path.split("/")
        if len(parts) == 1:
            return AwamUri(backend=self.backend, path="", query={})
        return AwamUri(backend=self.backend, path="/".join(parts[:-1]), query={})

    def to_string(self) -> str:
        path = self.path
        # Keep drive-letter colons readable: awam://local/G:/foo
        encoded_path = "/".join(quote(seg, safe=":@!$&'()*+,;=") for seg in path.split("/")) if path else ""
        base = f"{SCHEME}://{self.backend}"
        if encoded_path:
            base = f"{base}/{encoded_path}"
        elif self.backend == "root":
            base = f"{SCHEME}://root/"
        qs = urlencode({k: v[0] for k, v in self.query.items() if v}, doseq=False)
        if qs:
            return f"{base}?{qs}"
        if self.backend and not encoded_path and self.backend != "root":
            return f"{base}/"
        return base if encoded_path or self.query else f"{base}/"


def _normalize_inner_path(path: str) -> str:
    path = path.replace("\\", "/").strip("/")
    # Collapse duplicate slashes but keep G:/ style
    while "//" in path:
        path = path.replace("//", "/")
    return path


def parse_awam_uri(value: str) -> AwamUri:
    raw = (value or "").strip()
    if not raw:
        return AwamUri(backend="root", path="", query={})

    # Accept bare Windows / UNC / POSIX paths as local
    if not raw.lower().startswith(f"{SCHEME}://"):
        if _looks_like_filesystem_path(raw):
            inner = raw.replace("\\", "/")
            # awam://local/G:/foo
            if len(inner) >= 2 and inner[1] == ":":
                return AwamUri(backend="local", path=_normalize_inner_path(inner), query={})
            if inner.startswith("//"):
                rest = _normalize_inner_path(inner.lstrip("/"))
                return AwamUri(backend="local", path=f"unc/{rest}" if rest else "unc", query={})
            if inner.startswith("/"):
                return AwamUri(backend="local", path=_normalize_inner_path(inner), query={})
        raise ValueError(f"Not an awam:// URI or filesystem path: {value!r}")

    # urlparse treats awam://local/G:/x as host=local, path=/G:/x — good
    # But awam://local/G:/x — on some parsers host=local, path=/G:/x
    parsed = urlparse(raw)
    if parsed.scheme.lower() != SCHEME:
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")

    backend = (parsed.netloc or "").strip().lower()
    path = unquote(parsed.path or "")
    query = parse_qs(parsed.query, keep_blank_values=True)

    if not backend or backend == "root":
        # awam:/// or awam://root/ or awam://
        rest = _normalize_inner_path(path)
        if rest and rest.split("/")[0] not in ("", "root"):
            # awam:///knowledge/... unlikely; treat netloc empty + path
            pass
        return AwamUri(backend="root", path="", query=query)

    return AwamUri(backend=backend, path=_normalize_inner_path(path), query=query)


def _looks_like_filesystem_path(value: str) -> bool:
    v = value.replace("\\", "/")
    if len(v) >= 2 and v[1] == ":":
        return True
    if v.startswith("//") or v.startswith("/"):
        return True
    return False


def join_uri(parent: str, name: str) -> str:
    uri = parse_awam_uri(parent)
    return uri.child(name).to_string()


def local_path_to_uri(path: str) -> str:
    inner = path.replace("\\", "/")
    if inner.startswith("//"):
        rest = _normalize_inner_path(inner.lstrip("/"))
        inner_path = f"unc/{rest}" if rest else "unc"
        return AwamUri(backend="local", path=inner_path, query={}).to_string()
    return AwamUri(backend="local", path=_normalize_inner_path(inner), query={}).to_string()


def uri_to_local_path(uri: AwamUri) -> str | None:
    if uri.backend != "local" or not uri.path:
        return None
    path = uri.path
    if path == "unc":
        return None
    if path.startswith("unc/"):
        rest = path[4:]
        if not rest:
            return None
        return "\\\\" + rest.replace("/", "\\")
    # G:/foo -> G:\foo
    if len(path) >= 2 and path[1] == ":":
        return path.replace("/", "\\")
    if path.startswith("//"):
        return path.replace("/", "\\")
    return path
