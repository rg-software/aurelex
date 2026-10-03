"""Command-line interface for the catalog tool.

Modes:

  import  published catalog -> catalog/source.json (authored metadata)
  build   catalog/source.json + files -> catalog/catalog.json (derived)
  diff    built catalog vs published -> what changed
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from typing import Any, Dict, Optional

from .core import (
    DEFAULT_BASE_URL,
    DEFAULT_RELEASE_TAG,
    CatalogError,
    build_catalog,
    diff_catalogs,
    import_catalog,
    load_source,
    validate_catalog,
)

DEFAULT_SOURCE = "catalog/source.json"
DEFAULT_CATALOG = "catalog/catalog.json"
DEFAULT_FILES_DIR = "dist"


def _read_json(ref: str) -> Dict[str, Any]:
    """Read JSON from a path, ``-`` (stdin), or an http(s) URL."""
    try:
        if ref == "-":
            return json.load(sys.stdin)
        if ref.lower().startswith(("http://", "https://")):
            with urllib.request.urlopen(ref, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        with open(ref, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise CatalogError(f"cannot read {ref}: {exc}") from exc


def _write_json(path: str, doc: Dict[str, Any]) -> None:
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if path == "-":
        sys.stdout.write(text)
        return
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _resolve(published_ref: Optional[str], catalog_path: str) -> str:
    return published_ref if published_ref else catalog_path


def _cmd_import(args: argparse.Namespace) -> int:
    published = _read_json(args.published)
    source = import_catalog(published, release_tag=args.release_tag, base_url=args.base_url)
    _write_json(args.out, source)
    print(f"wrote {args.out}: {len(source['entries'])} entries", file=sys.stderr)
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    source = load_source(args.source)
    catalog = build_catalog(source, args.files_dir, updated=args.updated)
    _write_json(args.out, catalog)
    total = sum(f["sizeBytes"] for e in catalog["entries"] for f in e["files"])
    print(
        f"wrote {args.out}: {len(catalog['entries'])} entries, "
        f"{total} bytes total",
        file=sys.stderr,
    )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    catalog = _read_json(args.catalog)
    validate_catalog(catalog)
    print(f"ok: {args.catalog}", file=sys.stderr)
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    built = _read_json(args.catalog)
    published = _read_json(_resolve(args.published, args.catalog))
    result = diff_catalogs(built, published)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for label in ("new_files", "changed_files", "removed_files"):
            for name in result[label]:
                print(f"{label[:-6]:>8}  {name}")
        for v in result["identity_violations"]:
            print(f"VIOLATION  {v}")
        print(
            f"{len(result['new_files'])} new, {len(result['changed_files'])} changed, "
            f"{len(result['removed_files'])} removed, "
            f"{len(result['unchanged_files'])} unchanged",
            file=sys.stderr,
        )

    if result["identity_violations"]:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build-catalog.py",
        description="Build and compare the remote dictionary catalog. "
        "catalog.json is derived; catalog/source.json is the authored source.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_import = sub.add_parser("import", help="published catalog -> source.json")
    p_import.add_argument("published", help="published catalog: path, - (stdin), or https URL")
    p_import.add_argument("--out", default=DEFAULT_SOURCE, help=f"output source (default {DEFAULT_SOURCE})")
    p_import.add_argument("--release-tag", default=DEFAULT_RELEASE_TAG)
    p_import.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p_import.set_defaults(func=_cmd_import)

    p_build = sub.add_parser("build", help="source.json + files -> catalog.json")
    p_build.add_argument("--source", default=DEFAULT_SOURCE)
    p_build.add_argument("--files-dir", default=DEFAULT_FILES_DIR,
                         help=f"directory holding the built files (default {DEFAULT_FILES_DIR})")
    p_build.add_argument("--out", default=DEFAULT_CATALOG)
    p_build.add_argument("--updated", default=None, help="YYYY-MM-DD; defaults to the source's or today")
    p_build.set_defaults(func=_cmd_build)

    p_diff = sub.add_parser("diff", help="built catalog vs published catalog")
    p_diff.add_argument("published", nargs="?", default=None,
                        help="published catalog (default: --catalog)")
    p_diff.add_argument("--catalog", default=DEFAULT_CATALOG, help="the built catalog to compare")
    p_diff.add_argument("--json", action="store_true", help="emit the full result as JSON")
    p_diff.set_defaults(func=_cmd_diff)

    p_validate = sub.add_parser("validate", help="check a catalog document's structure")
    p_validate.add_argument("catalog", nargs="?", default=DEFAULT_CATALOG)
    p_validate.set_defaults(func=_cmd_validate)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
