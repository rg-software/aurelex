## Why

`scripts/kaikki-to-dsl.py` is 4245 lines and its test file 3573, with the
organization kept in section comments that only an insider reads. It grew by
accretion — profiles, audio planning, the prefetcher, the renderer, the CLI —
and every new language or feature lands in the same file, which makes review
diffs and merge conflicts worse each time.

## What Changes

- Split the tool into the `scripts/kaikki/` package, one module per concern
  (constants, profiles, dictzip, dsltext, snapshot, source, audio, render,
  preview, inputs, build, prefetch, cli), moving three helpers to break the one
  import cycle.
- Keep `scripts/kaikki-to-dsl.py` as a thin launcher, so every documented
  command (`python scripts/kaikki-to-dsl.py ...`) is unchanged.
- Make `kaikki` a flat facade that re-exports every name and propagates
  attribute writes to the modules holding them, so the test suite and callers
  patch `kaikki.download_cached` exactly as they did before.

## Capabilities

No spec change: this is a behaviour-preserving refactor. `skip_specs: true`.

## Impact

- `scripts/kaikki/*.py` (new package), `scripts/kaikki-to-dsl.py` (now a
  launcher).
- `scripts/tests/test_kaikki_to_dsl.py`: the loader imports the package; the 188
  test bodies are unchanged.
- `docs/KAIKKI-CONVERSION.md`: a module map.
