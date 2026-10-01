## Why

The Dicts row shows the dictionary's own name — for a DSL build, `#NAME`, which
is canonical English by design. So a Russian user sees an English name for their
Russian dictionary. The dictionary is distributed through the catalog we control,
so the catalog is the natural place to carry a display name per language: the
publisher supplies the wording, and the app shows the one matching its UI
language. This needs no change to the dictionary file and no per-language
templates in the converter.

## What Changes

- Extend a catalog entry with optional **localized display names** (a map from
  language code to name) alongside the existing `name`, which becomes the
  fallback.
- Show a catalog entry's name in the app's active language in the catalog pane.
- For an installed catalog dictionary, prefer its entry's name in the active
  language in the Dicts list, falling back to the dictionary's own name.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `remote-dictionary-catalog`: the catalog presentation shows the entry name in
  the app's active language when the entry provides one.
- `dictionary-management`: the dictionary display metadata prefers an installed
  catalog entry's localized name.

## Impact

- `app/RemoteCatalog.{hpp,cpp}`: parse the localized names; expose the active
  one. `app/main.qml`: use it in the catalog pane and the Dicts row.
  `docs/REMOTE-CATALOG.md`: the manifest field.
- `app/tests/CatalogTest.cpp`: parsing/selection tests.
- No converter change; the dictionary's own metadata stays canonical English.
