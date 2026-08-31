## Why

DSL (`.dsl`/`.dsl.dz`) was declared in the v1 format list, but the compressed
`.dsl.dz` (dictzip) path was never exercised with a real file — the archived
change's task 2.5 only tested uncompressed `.dsl`. Compressed DSL packs are
common in the wild (older Lingvo rips are usually shipped as `.dsl.dz`), so we
need example fixtures plus an on-device verification gate before claiming
support.

## What Changes

- Ship 2–3 small **example dictionaries** in `examples/dictionaries/` (one per
  interesting shape: plain EN with DSL markup, a bilingual EN↔RU pack, and a
  multi-word-headword phrasebook), each with a `.dsl.dz` compressed variant.
- Add a reproducible **generator** (`scripts/make-example-dicts.py`) that writes
  the `.dsl` files and produces **real dictzip** `.dsl.dz` files (RFC 1952 gzip
  with the dictd "RA" random-access extra field + per-chunk sync flushes — the
  format the engine's `dictzip.c` reader requires; plain gzip would not load).
- **Verify** the compressed path end-to-end on host (scan → lookup → HTML) and
  record the on-device verification as an open task (the app-side `.dsl.dz`
  scan filter is already present; this closes the test gap).
- Fix anything the verification surfaces (the scan filter, SAF staging for
  `.dz`, or the engine carve) only if needed — expected to be a no-op.

## Capabilities

### New Capabilities

None — this is developer tooling and fixtures, not a user-facing behavior
change.

### Modified Capabilities

None — `.dsl.dz` is already within the archived `dictionary-management` scope
(its format list names `DSL .dsl/.dsl.dz`); no requirement changes.

This change therefore sets `skip_specs: true` (fixtures + verification only).

## Impact

- `examples/dictionaries/*.dsl{, .dz}` — new content for manual/device testing
  and the smoke fixture set.
- `scripts/make-example-dicts.py` — new generator (dictzip writer included).
- `app/src/main/cpp/engine/gd_boundary.cc` — only if verification finds the
  `.dsl.dz` filter/suffix handling needs a change.
- CI smoke (`.github/workflows/engine-smoke.yml`) — optionally extend the
  fixture set to include a `.dsl.dz` and assert it loads.
