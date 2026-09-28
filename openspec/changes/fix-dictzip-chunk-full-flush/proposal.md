## Why

Generated `.dsl.dz` files are unreadable past their first chunk.

`make_dictzip` (`scripts/make-example-dicts.py`) terminated each 16 KiB chunk of
the deflate stream with a **sync** flush (`Z_SYNC_FLUSH`). A sync flush flushes
pending output but keeps the compression history, so a later chunk's
back-references reach into an earlier chunk. The engine random-accesses a
`.dsl.dz`: it seeks to a chunk and inflates just that chunk, so once the history
it needs is in another chunk it fails.

Verified on the reported 11-chunk dictionary (159873 bytes uncompressed): chunk 0
inflates, chunks 1-9 each fail with `invalid distance too far back`. On device the
app showed `DICTZIP error: inflate: invalid distance too far back` when reading an
article, and the dictionary was unusable for anything past the first chunk.

Only dictionaries whose uncompressed DSL exceeds one chunk (16 KiB) are affected.
That is why it was never caught: the committed and smoke fixtures are all a
single chunk, so their chunk 0 is the whole stream and there is no cross-chunk
back-reference to make.

`kaikki-to-dsl.py` imports this writer ("single source of truth"), so both the
sample fixtures and the real conversions are affected by the one function.

## What Changes

- **Terminate each dictzip chunk with a full flush.** `Z_FULL_FLUSH` resets the
  deflate history at every chunk boundary, so every chunk inflates from a cold
  start - which is what a seeking reader does. The `RA` chunk index, the chunk
  length, and the deterministic, byte-identical output property are unchanged.
- **Guard it with a test that reads the way the engine does.** The existing tests
  decompress the whole stream with `gzip`, which cannot see the defect; the new
  test parses the `RA` chunk index and inflates each chunk independently, so a
  sync-flush regression fails with the same error the device showed.

The committed example `.dsl.dz` fixtures are **not** regenerated here. They are
single-chunk, so they read correctly as they stand, and regenerating them would
also apply two earlier generator changes that were never propagated to the
committed copies (`[/opt]` -> `[/*]`, and the `badge` resource entry) - unrelated
content churn that belongs in its own fixture-refresh change.

No app or engine change: the reader is upstream and is behaving correctly
(seeking to a chunk and inflating it), and the boundary does not touch dictzip.
This is a defect in the tool that produces the content.

## Capabilities

### Modified Capabilities

- `dictionary-conversion`: "Import-ready, deterministic packaging" requires a
  dictzip-compressed `.dsl.dz` but says nothing about how the chunks must be
  delimited, which is exactly the property the reader depends on. It gains the
  requirement that every chunk be independently inflatable so the reader can
  seek, plus the scenario that pins it.

## Impact

- Affected code:
  - `scripts/make-example-dicts.py` - `make_dictzip` chunk flush.
  - `scripts/tests/test_kaikki_to_dsl.py` - a `DictzipTests` case that inflates
    each chunk independently (and a stream round-trip).
- Affected APIs: none. No `gd_*` boundary function changes; no app or engine code.
- Affected dependencies: none.
- Upstream fidelity: `engine/` unchanged.
- Localization: no catalogs touched.
- Content effect: existing dictionaries built with the old writer must be
  regenerated (their DSL content is unchanged; only the compression framing is
  corrected). A `.dsl.dz` can also be repaired by decompressing it and re-running
  the fixed writer, which is how the reported dictionary was verified.
