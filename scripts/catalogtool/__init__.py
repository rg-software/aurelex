"""Build and compare the remote dictionary catalog.

`catalog.json` is a derived artifact. The authored source of truth for entry
metadata is ``catalog/source.json``; the source of truth for content is the
built dictionary files (by default under ``dist/``). `core.build_catalog` joins
them, computing each file's ``sizeBytes``, ``sha256`` and release-asset ``url``.

See ``docs/REMOTE-CATALOG.md`` for the maintainer workflow and
``openspec/changes/public-catalog-hosting/`` for the design.
"""

from __future__ import annotations

from .core import (
    DEFAULT_BASE_URL,
    DEFAULT_RELEASE_TAG,
    KNOWN_ROLES,
    MAX_ASSET_BYTES,
    SCHEMA_VERSION,
    CatalogError,
    build_catalog,
    diff_catalogs,
    file_url,
    import_catalog,
    load_source,
    sha256_file,
    validate_catalog,
    validate_source,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_RELEASE_TAG",
    "KNOWN_ROLES",
    "MAX_ASSET_BYTES",
    "SCHEMA_VERSION",
    "CatalogError",
    "build_catalog",
    "diff_catalogs",
    "file_url",
    "import_catalog",
    "load_source",
    "sha256_file",
    "validate_catalog",
    "validate_source",
]
