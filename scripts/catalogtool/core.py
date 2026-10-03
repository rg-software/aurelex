"""Core catalog logic: validate, build, import, diff.

Pure functions over plain dicts, so the CLI and the unit tests share one
implementation. No filesystem mutation happens here except reading the file
bytes whose size and digest are the catalog's derived fields.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
from typing import Any, Dict, List

SCHEMA_VERSION = 1
DEFAULT_RELEASE_TAG = "catalog-data"
DEFAULT_BASE_URL = "https://github.com/rg-software/aurelex/releases/download"
# GitHub refuses to host a single release asset larger than 2 GiB.
MAX_ASSET_BYTES = 2 * 1024 * 1024 * 1024
KNOWN_ROLES = ("dictionary", "resources")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class CatalogError(Exception):
    """The source, a referenced file, or a document cannot be published."""


def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise CatalogError(msg)


def _is_basename(name: Any) -> bool:
    return (
        isinstance(name, str)
        and bool(name)
        and "/" not in name
        and "\\" not in name
        and name not in (".", "..")
    )


def sha256_file(path: str, chunk: int = 1024 * 1024) -> str:
    """SHA-256 of a file, streamed so a multi-GB file is never held in memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def file_url(base_url: str, release_tag: str, name: str) -> str:
    return base_url.rstrip("/") + "/" + release_tag.strip("/") + "/" + name


def validate_source(source: Dict[str, Any]) -> None:
    """Check an authored source document. Raises CatalogError on any problem."""
    _require(isinstance(source, dict), "source is not an object")
    tag = source.get("releaseTag", DEFAULT_RELEASE_TAG)
    _require(isinstance(tag, str) and bool(tag.strip()),
             "source: releaseTag must be a non-empty string")
    base = source.get("baseUrl", DEFAULT_BASE_URL)
    _require(isinstance(base, str) and base.lower().startswith("https://"),
             "source: baseUrl must be an https:// URL")
    entries = source.get("entries")
    _require(isinstance(entries, list), "source: entries must be an array")

    seen_ids = set()
    seen_names = set()
    for i, e in enumerate(entries):
        where = f"entries[{i}]"
        _require(isinstance(e, dict), f"{where}: not an object")
        eid = e.get("id")
        _require(isinstance(eid, str) and bool(eid), f"{where}: id must be a non-empty string")
        _require(bool(_ID_RE.match(eid)), f"{where}: invalid id {eid!r}")
        _require(eid not in seen_ids, f"{where}: duplicate id {eid!r}")
        seen_ids.add(eid)

        for key in ("name", "langFrom", "langTo"):
            v = e.get(key)
            _require(isinstance(v, str) and bool(v.strip()),
                     f"{where}: {key} must be a non-empty string")
        # Names are the key the app records installed digests under (the
        # download service reports success by entry name), so they must not
        # collide: a duplicate would make the recorded content ambiguous.
        _require(e["name"] not in seen_names,
                 f"{where}: duplicate entry name {e['name']!r}")
        seen_names.add(e["name"])
        names = e.get("names")
        if names is not None:
            _require(isinstance(names, dict), f"{where}: names must be an object")
            for k, v in names.items():
                _require(isinstance(v, str) and bool(v.strip()),
                         f"{where}: names[{k!r}] must be a non-empty string")

        files = e.get("files")
        _require(isinstance(files, list) and bool(files),
                 f"{where}: files must be a non-empty array")
        seen_file_names = set()
        has_required_dictionary = False
        for j, f in enumerate(files):
            fwhere = f"{where} files[{j}]"
            _require(isinstance(f, dict), f"{fwhere}: not an object")
            role = f.get("role")
            _require(role in KNOWN_ROLES, f"{fwhere}: role must be one of {KNOWN_ROLES}")
            _require(isinstance(f.get("required"), bool),
                     f"{fwhere}: required must be a boolean")
            name = f.get("name")
            _require(_is_basename(name), f"{fwhere}: name must be a plain basename")
            _require(name not in seen_file_names, f"{fwhere}: duplicate file name {name!r}")
            seen_file_names.add(name)
            if role == "dictionary" and f["required"]:
                has_required_dictionary = True
        _require(has_required_dictionary,
                 f'{where}: needs at least one required "dictionary" file')


def load_source(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        source = json.load(f)
    source.setdefault("releaseTag", DEFAULT_RELEASE_TAG)
    source.setdefault("baseUrl", DEFAULT_BASE_URL)
    validate_source(source)
    return source


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_catalog(catalog: Dict[str, Any]) -> None:
    """Check a built/published catalog document for structural correctness.

    Does not require the referenced files (so CI can validate the committed
    document without the multi-GB assets); it checks the shape the app's parser
    depends on.
    """
    _require(isinstance(catalog, dict), "catalog is not an object")
    _require(catalog.get("schemaVersion") == SCHEMA_VERSION,
             f"catalog: schemaVersion must be {SCHEMA_VERSION}")
    entries = catalog.get("entries")
    _require(isinstance(entries, list), "catalog: entries must be an array")

    seen_ids = set()
    for i, e in enumerate(entries):
        where = f"entries[{i}]"
        _require(isinstance(e, dict), f"{where}: not an object")
        eid = e.get("id")
        _require(isinstance(eid, str) and bool(eid), f"{where}: id must be a non-empty string")
        _require(eid not in seen_ids, f"{where}: duplicate id {eid!r}")
        seen_ids.add(eid)
        for key in ("name", "langFrom", "langTo"):
            v = e.get(key)
            _require(isinstance(v, str) and bool(v.strip()),
                     f"{where}: {key} must be a non-empty string")
        files = e.get("files")
        _require(isinstance(files, list) and bool(files),
                 f"{where}: files must be a non-empty array")
        seen_file_names = set()
        has_required_dictionary = False
        for j, f in enumerate(files):
            fwhere = f"{where} files[{j}]"
            _require(isinstance(f, dict), f"{fwhere}: not an object")
            _require(f.get("role") in KNOWN_ROLES, f"{fwhere}: unknown role")
            _require(isinstance(f.get("required"), bool), f"{fwhere}: required must be a boolean")
            _require(_is_basename(f.get("name")), f"{fwhere}: name must be a plain basename")
            _require(f["name"] not in seen_file_names, f"{fwhere}: duplicate file name {f['name']!r}")
            seen_file_names.add(f["name"])
            url = f.get("url")
            _require(isinstance(url, str) and url.lower().startswith("https://"),
                     f"{fwhere}: url must be https://")
            size = f.get("sizeBytes")
            _require(isinstance(size, int) and not isinstance(size, bool) and size > 0,
                     f"{fwhere}: sizeBytes must be a positive integer")
            _require(isinstance(f.get("sha256"), str) and bool(_SHA256_RE.match(f["sha256"])),
                     f"{fwhere}: sha256 must be 64 lowercase hex characters")
            if f["role"] == "dictionary" and f["required"]:
                has_required_dictionary = True
        _require(has_required_dictionary,
                 f'{where}: needs at least one required "dictionary" file')


def build_catalog(
    source: Dict[str, Any],
    files_dir: str,
    updated: str | None = None,
    max_asset_bytes: int | None = None,
) -> Dict[str, Any]:
    """Join the authored source with the built files into a catalog document.

    Computes ``sizeBytes`` and ``sha256`` for every file and derives its URL for
    the permanent release tag. Raises CatalogError if a file is missing, empty,
    or larger than the release-asset cap.
    """
    limit = MAX_ASSET_BYTES if max_asset_bytes is None else max_asset_bytes
    tag = source.get("releaseTag", DEFAULT_RELEASE_TAG)
    base = source.get("baseUrl", DEFAULT_BASE_URL)

    out_entries: List[Dict[str, Any]] = []
    for e in source["entries"]:
        files_out: List[Dict[str, Any]] = []
        for f in e["files"]:
            name = f["name"]
            path = os.path.join(files_dir, name)
            if not os.path.isfile(path):
                raise CatalogError(f"entry {e['id']}: file not found: {path}")
            size = os.path.getsize(path)
            if size <= 0:
                raise CatalogError(f"entry {e['id']}: {name} is empty")
            if size > limit:
                raise CatalogError(
                    f"entry {e['id']}: {name} is {size} bytes, over the "
                    f"{limit}-byte release-asset cap"
                )
            files_out.append({
                "role": f["role"],
                "required": f["required"],
                "name": name,
                "url": file_url(base, tag, name),
                "sizeBytes": size,
                "sha256": sha256_file(path),
            })

        entry: Dict[str, Any] = {"id": e["id"], "name": e["name"]}
        if e.get("names"):
            entry["names"] = e["names"]
        entry["langFrom"] = e["langFrom"]
        entry["langTo"] = e["langTo"]
        if e.get("attribution") is not None:
            entry["attribution"] = e["attribution"]
        if e.get("license") is not None:
            entry["license"] = e["license"]
        entry["files"] = files_out
        out_entries.append(entry)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "updated": updated or source.get("updated") or _today(),
        "entries": out_entries,
    }


def import_catalog(
    published: Dict[str, Any],
    release_tag: str = DEFAULT_RELEASE_TAG,
    base_url: str = DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    """Turn an already-published catalog into an authored source document.

    Drops the derived fields (``url``, ``sizeBytes``, ``sha256``) so authoring
    starts from the live catalog rather than a blank page.
    """
    _require(isinstance(published, dict), "published catalog is not an object")
    entries = published.get("entries")
    _require(isinstance(entries, list), "published catalog: entries must be an array")

    out_entries: List[Dict[str, Any]] = []
    for i, e in enumerate(entries):
        _require(isinstance(e, dict), f"published entries[{i}] is not an object")
        entry: Dict[str, Any] = {"id": e.get("id"), "name": e.get("name")}
        if isinstance(e.get("names"), dict) and e["names"]:
            entry["names"] = dict(e["names"])
        entry["langFrom"] = e.get("langFrom")
        entry["langTo"] = e.get("langTo")
        if isinstance(e.get("attribution"), str) and e["attribution"]:
            entry["attribution"] = e["attribution"]
        if isinstance(e.get("license"), str) and e["license"]:
            entry["license"] = e["license"]

        files = e.get("files")
        _require(isinstance(files, list) and bool(files),
                 f"published entries[{i}]: files must be a non-empty array")
        files_out = []
        for j, f in enumerate(files):
            _require(isinstance(f, dict),
                     f"published entries[{i}] files[{j}] is not an object")
            files_out.append({
                "role": f.get("role"),
                "required": f.get("required"),
                "name": f.get("name"),
            })
        entry["files"] = files_out
        out_entries.append(entry)

    source = {
        "releaseTag": release_tag,
        "baseUrl": base_url,
        "entries": out_entries,
    }
    validate_source(source)
    return source


def _index_files(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for e in catalog.get("entries", []):
        for f in e.get("files", []):
            idx[f["name"]] = {
                "entry": e["id"],
                "size": f.get("sizeBytes"),
                "sha256": f.get("sha256"),
            }
    return idx


def diff_catalogs(built: Dict[str, Any], published: Dict[str, Any]) -> Dict[str, Any]:
    """Classify the built document against the published one.

    Reports which files are new, changed, unchanged, or removed, plus any
    identity violation: an entry's published file name that is gone (renamed or
    removed), or a file name that moved between entries. Callers upload only the
    new/changed files and always republish the (tiny) catalog document.
    """
    b = _index_files(built)
    p = _index_files(published)

    new, changed, unchanged = [], [], []
    for name, info in b.items():
        if name not in p:
            new.append(name)
        elif p[name]["sha256"] != info["sha256"] or p[name]["size"] != info["size"]:
            changed.append(name)
        else:
            unchanged.append(name)
    removed = [name for name in p if name not in b]

    violations: List[str] = []
    built_entries = {e["id"]: e for e in built.get("entries", [])}
    for e in published.get("entries", []):
        bu = built_entries.get(e["id"])
        if bu is None:
            continue
        built_names = {f["name"] for f in bu.get("files", [])}
        for f in e.get("files", []):
            if f["name"] not in built_names:
                violations.append(
                    f"entry {e['id']}: published file {f['name']!r} is gone "
                    f"(renamed or removed)"
                )
    for name, info in p.items():
        if name in b and b[name]["entry"] != info["entry"]:
            violations.append(
                f"file {name!r} moved from entry {info['entry']!r} "
                f"to {b[name]['entry']!r}"
            )

    changed_entries = sorted(
        {b[n]["entry"] for n in changed + new} | {p[n]["entry"] for n in removed}
    )
    return {
        "changed_files": sorted(changed),
        "new_files": sorted(new),
        "removed_files": sorted(removed),
        "unchanged_files": sorted(unchanged),
        "changed_entries": changed_entries,
        "identity_violations": violations,
    }
