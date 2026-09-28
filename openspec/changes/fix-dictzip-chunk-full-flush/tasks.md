## 1. Root cause

- [x] 1.1 Confirm `make_dictzip` terminated each chunk with `Z_SYNC_FLUSH`, which keeps the deflate history
- [x] 1.2 Confirm the engine random-accesses chunks (chunk 0 inflates, chunks 1-9 fail with `invalid distance too far back` on the reported 11-chunk file)
- [x] 1.3 Confirm the device symptom: `DICTZIP error: inflate: invalid distance too far back` reading an article
- [x] 1.4 Confirm the existing tests cannot see it: `read_dz` decompresses the whole stream with `gzip`

## 2. Fix

- [x] 2.1 Change the chunk flush in `make_dictzip` from `Z_SYNC_FLUSH` to `Z_FULL_FLUSH` and correct the docstring
- [x] 2.2 Confirm the `RA` index, chunk length, and byte-identical determinism are unchanged

## 3. Regression guard

- [x] 3.1 Add `DictzipTests` to `scripts/tests/test_kaikki_to_dsl.py`: parse the `RA` subfield and inflate every chunk with a fresh decompressor (the engine's read)
- [x] 3.2 Assert the chunk outputs sum to the input, and add a full-stream round-trip
- [x] 3.3 Verify both ways: `Z_SYNC_FLUSH` makes the test error with `invalid distance too far back`; `Z_FULL_FLUSH` passes
- [x] 3.4 Run the whole converter suite (`python -m unittest discover -s scripts/tests`) and confirm it is green

## 4. Regenerate fixtures and verify on device

- [ ] 4.1 Regenerate the committed `examples/dictionaries/*.dsl.dz` - deferred: they are single-chunk (so they read correctly as-is; chunk 0 is the whole stream, so there is no cross-chunk reference), and regenerating them also picks up two earlier generator changes (`[/opt]` -> `[/*]` and the `badge` resource entry) that were never applied to the committed copies. That content churn would muddy this change; do it as a separate fixture-refresh change.
- [ ] 4.2 Regenerate `examples/kaikki-sample/*.dsl.dz` - deferred for the same reason.
- [x] 4.3 Repackage the reported `.dsl.dz` (decompress + rewrite) and confirm every chunk inflates independently
- [x] 4.4 Install the repaired file on the device and confirm the Search dropdown and the article for `swop` render with no DICTZIP error
- [ ] 4.5 Confirm a fresh `kaikki-to-dsl.py` run produces a readable multi-chunk dictionary end to end
