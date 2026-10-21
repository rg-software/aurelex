## Why

Indexing a card under several headwords (`--index-readings`, `--include-inflections`)
made lookups resolve that the article cannot attribute: a kana lookup of けんでん
fans out to ten homophone cards (喧伝, 検田, 検電, …), and no article names the
headword it belongs to — the engine header shows only the dictionary, the app
only the query. Before alias headwords existed the lookup key always was the
headword, so no label was needed; now kana results read as an unattributed wall
of repeated readings.

## What Changes

- A card emitted under more than one headword SHALL open with its primary
  (base-form) headword as a title line, so every article that an alias lookup
  reaches says which word it defines.
- Cards with a single headword SHALL render exactly as today (no title line),
  so the shipped English/Russian dictionaries rebuild byte-identically.
- Converter-only (`render.py`): no engine, app, boundary, or manifest change.
  The app cannot supply the label (it knows the query, not the headword), and
  an engine-side label would route through `patches/` for what the converter
  can do alone.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-conversion`: "Card article layout" gains the alias-card title
  rule (primary headword labelled when a card carries alias headwords).

## Impact

- `scripts/kaikki/render.py` (title emission), `scripts/tests/` (title present
  on alias cards, absent on single-headword cards, determinism preserved),
  `docs/KAIKKI-CONVERSION.md` (article-shape section).
- Rebuild + republish of `au_kaikki_ja-ja` afterwards; its digest change flows
  through the installed-dictionary update lifecycle, which doubles as the
  on-device verification for this change.
- No engine, app, or boundary code is touched.
