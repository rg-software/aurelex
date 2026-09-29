## 1. Shared fetch core

- [x] 1.1 Extract the per-file fetch out of `prefetch_audio` into a helper that attempts one download, classifies the failure as permanent or transient via the existing `failure_is_permanent`/`describe_failure`, records a permanent one in the run's dead log, and returns the classification plus a human reason
- [x] 1.2 Extract the run summary and its exit-status rule (complete vs. `--limit` vs. transient) into a small accumulator both fetch modes render, so the wording is identical in both
- [x] 1.3 Confirm the refactor leaves `prefetch-audio` byte-for-byte equivalent in behaviour: same summary text, same exit codes, same dead-file handling (`python -m unittest scripts.tests.test_kaikki_to_dsl.AudioPrefetchTests` passes unchanged)

## 2. Shard planning

- [x] 2.1 Add `--split N` to the prefetch parser; it implies listing (no download) and rejects a value below 1 with a clear message
- [x] 2.2 Derive shard paths from the manifest path (`missing.tsv` → `missing.shard-01-of-04.tsv`), zero-padded to the width of N, and write a leading comment line in each shard naming the options the shard was planned with (`--source-lang`, `--audio-per-word`, `--audio-lang`, snapshot)
- [x] 2.3 Route each name the manifest *accepts* to shard `accepted % N` as it is found, so the shards are disjoint and their counts differ by at most one, with no second pass and no buffering
- [x] 2.4 Leave no shard file behind when a run has nothing outstanding (`TabularLog`'s lazy open already does this; assert it)
- [x] 2.5 Reject `--split` together with options it contradicts, rather than silently ignoring one of them

## 3. `fetch-list` worker mode

- [x] 3.1 Add a `fetch_list` parser and a `fetch-list` mode word in `main()`, next to `prefetch-audio`; take the list file as a positional argument and require `--into <dir>`, with no snapshot options at all
- [x] 3.2 Read the list as a generator, parsing `name<TAB>url`, ignoring blank lines and `#` comments, tolerating a third column, and failing with the line number on a line with no tab
- [x] 3.3 Resolve each name with `os.path.join(into, *name.split("/"))` so a shard planned on one OS is usable on another
- [x] 3.4 Drive the shared fetch helper over the generator with `--timeout/--spacing/--retries/--max-backoff/--force-download`, and `--limit` bounding *attempts* as it does in the prefetcher
- [x] 3.5 Write the dead list to `<list>.dead.tsv` by default (overridable), never inside the cache directory, and never fetch a replacement for a permanently-gone file
- [x] 3.6 Report the same summary shape as the prefetcher — fetched/attempted, gone-with-reasons, transient, and a "done" line when the shard is exhausted — and return the same exit-status convention

## 4. Tests

- [x] 4.1 Shards are disjoint, complete against the unsharded manifest, and balanced to within one file, for N from 1 to more shards than files
- [x] 4.2 `--split` downloads nothing and overrides/contradicts `--limit` the way `--list` does
- [x] 4.3 A worker fetches a shard into an empty directory and every listed file lands with a valid `.sha256` sidecar, requesting nothing else
- [x] 4.4 Re-fetching a shard skips files already present and verified, and requesting no URL for them
- [x] 4.5 A 404 in a shard is written to the worker's dead list with its reason, is not retried by that worker, and does not trigger a replacement fetch
- [x] 4.6 A malformed line (no tab) fails with its line number instead of being skipped
- [x] 4.7 The whole user flow, end to end and offline: `build (gaps) → plan with --split → fetch-list per shard → copy the worker caches together → re-run prefetch-audio locally → build`, asserting the final build makes no request, bundles the union, and that the closing re-run requested nothing and reported done
- [x] 4.8 The closing re-run after a deliberately incomplete worker fetch requests the missing file, so a partial parallel run is finished rather than left with a gap
- [x] 4.9 Files already in the local cache are absent from the work and from every shard, and the already-held count is reported
- [x] 4.10 Copying a cache over itself leaves every file verified and triggers no download

## 5. Documentation

- [x] 5.1 Add the multi-machine workflow to `docs/KAIKKI-CONVERSION.md` as the five steps the user actually performs: plan with `--split N`, hand out shard files, `fetch-list` per machine, copy the worker caches together into `<cache>/<dump-date>/audio-cache/`, re-run `prefetch-audio` locally, then build
- [x] 5.2 State before the commands that the speedup is per client: machines sharing one NAT egress IP share the rate limit and gain nothing
- [x] 5.3 Say plainly that the closing local re-run is the check — a correct set of worker caches makes it request nothing and report done — and that it is also what finishes a partial parallel run
- [x] 5.4 Document that a worker cache must be copied *into* the building machine's own cache directory (the one the build reads), and that a lost `<list>.dead.tsv` costs re-requests in the closing pass rather than correctness
- [x] 5.5 Document that one plan per option set is required, because shards from different option sets may overlap
- [x] 5.6 Document the D4 trade-off: a file gone during a sharded fetch is left to the build's slot-fill, so a build with `--no-audio-download` may show fewer than `--audio-per-word` recordings for the affected headwords
- [x] 5.7 Add `fetch-list` to the build's `--help` epilog alongside the `prefetch-audio` example, and to the prefetcher's epilog notes

## 6. Validation

- [x] 6.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` (full suite) and confirm no existing test needed changing as a result of 1.1–1.3
- [x] 6.2 Run `openspec validate kaikki-sharded-audio-prefetch` and resolve any findings