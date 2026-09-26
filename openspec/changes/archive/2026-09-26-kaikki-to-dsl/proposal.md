## Why

Kaikki.org publishes machine-readable Wiktionary extracts (wiktextract JSONL)
plus a ~20 GB pronunciation-audio archive, but Aurelex can only import
mdict/DSL/StarDict and there is no desktop path that turns those extracts into
an importable dictionary. A reproducible converter lets a user build an offline
dictionary for their own language pair (`en/en`, `en/ru`, …) on a computer and
copy it to the phone through the existing folder import — without the project
redistributing any dictionary.

## What Changes

- Add a **desktop batch tool** (Python) that, from a pinned kaikki.org snapshot,
  reproducibly downloads the raw JSONL and the audio archive, then builds a DSL
  dictionary for a user-specified language pair.
- **Headword policy:** base forms are the only indexed headwords by default;
  inflected/`form_of` entries are not indexed but their forms are rendered
  inside the base article. A flag (`--include-inflections`) additionally indexes
  inflected forms so they are directly findable (at the cost of appearing in the
  suggestion list).
- **Article content:** glosses (and translations for bilingual pairs), grammar
  forms of the base word, and bounded pronunciation audio.
- **Bounded audio:** at most N audio files per headword (`--audio-per-word`,
  default 3; `0`/`--no-audio` disables), deduplicated, language-preferred.
- **Sample/preview mode:** emit a small `.dsl` (and optional HTML preview) so the
  article shape and formatting can be reviewed before a full run.
- **Provenance:** a `#NAME`/attribution block and an about card citing Wiktionary
  (CC BY-SA 4.0) and wiktextract, always embedded in the output.
- **Packaging:** a deterministic dictzip-compressed `.dsl.dz` (no plain `.dsl`)
  plus referenced audio bundled as a sibling resource, by default a single
  `.dsl.dz.files.zip` archive, ready for the existing SAF folder import.
- **No app or engine changes:** DSL parsing, `.dsl.dz` dictzip, and `.files`
  audio resolution already exist.

## Capabilities

### New Capabilities

- `dictionary-conversion`: reproducible conversion of kaikki.org Wiktionary
  extracts into an Aurelex-importable DSL dictionary for a chosen language pair,
  covering snapshot download, pair filtering, base-form headword selection,
  opt-in inflected-form indexing, article rendering, bounded audio bundling,
  sample/preview output, and embedded provenance.

### Modified Capabilities

None — this adds a desktop converter; it does not change app or engine
requirements. The output is consumed by the existing `dictionary-management`
import path unchanged.

## Impact

- New tooling under `scripts/` (or `tools/`) plus a short usage doc; no app,
  QML, or carve/engine code changes.
- Output is a derivative work of Wiktionary (CC BY-SA 4.0) and carries the
  required attribution; the repository itself still ships no data.
- Consumes the existing `dictionary-management` import path (DSL + `.files`).
- Adds a Python dependency surface for the tool only (not for the Android app).
