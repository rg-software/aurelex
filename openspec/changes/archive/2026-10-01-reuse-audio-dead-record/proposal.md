## Why

A recording Wikimedia reports permanently gone (404/410/451) is discovered
afresh on almost every run, so a build spends time re-asking for files that can
never come back:

- The **build keeps no dead record at all** — `audio-dead.tsv` is written and
  read only by `prefetch-audio`, so every rebuild re-attempts every 404 it has
  ever seen.
- The prefetcher's record is **compared wrongly**: the file stores the name as
  written (`En-us-quadrilateral.ogg`, capitalised, as MediaWiki spells it), while
  the lookup folds it to a match key (`en-us-quadrilateral.ogg`). The two never
  equal, so the skip never fires for any real Wikimedia name — only for the
  all-lowercase names the tests happen to use.
- A worker re-running a shard re-requests the names its own `<shard>.dead.tsv`
  already records, which the spec already says it should not.

## What Changes

- **Fold dead-file names to match keys when loading them**, so a recorded-gone
  recording is actually skipped by the prefetcher.
- **Have `fetch-list` skip the names its `<shard>.dead.tsv` already holds**, so a
  second pass over a shard is cheap.
- **Have the build share `<snapshot>/audio-dead.tsv`**: read it to skip what an
  earlier run recorded gone, and append a recording it finds permanently gone,
  so a 404 costs one attempt ever rather than one per rebuild.

A skipped recording is still counted among those missing, so a build's shortfall
reads the same every run; only the repeated request goes away.

## Capabilities

Adds a requirement to **sharded-audio-prefetch**: one dead record, honoured by
every run. It also makes true an existing scenario ("is not retried by that
worker again") that the code did not satisfy.

## Impact

- `scripts/kaikki-to-dsl.py`: `AudioPlan` (dead set + `on_gone`), `build`,
  `AudioWishlist`, `fetch_list`, `FetchTally`.
- `scripts/tests/test_kaikki_to_dsl.py`.
- `docs/KAIKKI-CONVERSION.md`.
