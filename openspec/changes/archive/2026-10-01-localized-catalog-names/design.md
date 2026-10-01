## Context

A catalog entry's display name is a single string (`RemoteCatalog::Entry::name`,
`docs/REMOTE-CATALOG.md`). It is shown in the catalog pane; after install the
Dicts row shows the engine's `getName()` instead (the dictionary's own name,
`#NAME` for a DSL build). The staging directory is keyed by the entry's
`contentHash`, and `RemoteCatalog::isInstalled` already matches an installed
dictionary to its entry, so the app can find an installed dictionary's entry.

## Goals / Non-Goals

**Goals**

- A publisher can give an entry a display name per language; the app shows the
  one matching its UI language.

**Non-Goals**

- Not localizing the language pair, the dictionary file's metadata, or its
  description — the pair and `.ann` stay canonical English (decided separately).
- No new catalog-side lifecycle action.

## Decisions

### D1: An optional localized-names map, `name` as fallback

The entry gains an optional map from language code to name (keyed by the UI
language's short code); `name` remains required and is the fallback. The app
picks the entry's name for its active UI language, else `name`. A missing or
malformed map falls back rather than failing the catalog load.

### D2: The app resolves the name; the file stays canonical

The dictionary's own name (and `#NAME`) stays a canonical English brand. The
localized presentation lives in the manifest, which the publisher controls, so
there is no per-language template in the converter and no app-side translation
table for names.

### D3: An installed dictionary looks up its entry

`RemoteCatalog`'s installed-detection (content hash) already links an installed
dictionary to its entry; the Dicts model consults it and shows the entry's
localized name when present. A folder-imported dictionary has no entry and keeps
its own name.

## Risks / Trade-offs

- **Only catalog dictionaries get a localized name.** Folder imports keep their
  own name. Acceptable: the catalog is the distribution channel; local imports are
  the developer's own builds.
- **The UI language must map to a code.** The plugin uses the locale's short code
  (`ru`, `ja`); an entry that lists only `ru` shows that for `ru-RU` too.
