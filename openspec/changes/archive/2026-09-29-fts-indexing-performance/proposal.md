## Why

While a large dictionary indexes, the UI itself stays responsive — the build runs
off-thread and progress is shown — but the app is not *searchable*: `gd_fts_index`
holds the global `g_engineMutex` for the entire `makeFTSIndex()` run, so every
lookup, scan, group edit, and removal blocks until the build finishes. Existing
dictionaries are already imported and indexed, yet they are unusable for minutes
while a newly added dictionary indexes. The existing spec promises the user "can
keep using the rest of the app" (`full-text-search`), which is only half-true:
responsive, but nothing can be looked up until indexing ends. On top of that, `makeFTSIndex` commits only once at
the very end — an interrupted build loses all work — and `compact()` rewrites the
whole index a second time. The app also disables the Dicts Remove button for the
whole processing chain, so a dictionary cannot be deleted while anything is
indexing.

## What Changes

- **FTS build interleaves with the engine.** The global `g_engineMutex` is held
  only for one bounded slice of the build at a time, released between slices, so
  lookups, scans, group edits, and dictionary removal proceed while a build
  runs and wait at most one slice. Engine access stays mutually exclusive — the
  build is interleaved, never parallel. The dictionary currently being built is
  withheld from lookup and full-text search until its index completes, which is
  behavior-preserving (today the whole engine is blocked for the build)
  (`full-text-search`, `dictionary-management`).
- **Interrupted builds keep their work.** The xapian build commits
  periodically instead of only at the end, so a killed/backgrounded build resumes
  from the last commit rather than restarting from zero, and peak memory no longer
  grows with the whole dictionary.
- **Automatic indexing is bounded.** A dictionary large enough that its build
  would dominate an import is not auto-indexed as part of the import chain; it is
  built when the user first runs a full-text search over it (the existing
  "Index build on demand" behavior, currently unimplemented).
- **Removal works at any time.** The Dicts Remove button is enabled during
  staging / scanning / indexing; removing a dictionary cancels its in-flight
  build (or drops it from the queue) and deletes its staged copy and index
  within a bounded time, without the user waiting for the batch to finish.
- **Diagnostic**: confirm from `gd_scan_dicts took %lld ms` that the
  mtime-based lookup-index cache is not silently rebuilding on every launch
  before attributing slowness to FTS.

Not in scope: pre-built desktop-generated index caches (separate proposal).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `full-text-search`: index build becomes interleaved with the rest of the
  engine (the lock is held per slice, not for the whole build) so lookups and
  searches over other dictionaries wait at most one indexing slice; the
  dictionary being built is withheld until its index completes; partial build
  work survives interruption; automatic bulk indexing is
  bounded/deferrable for very large dictionaries and the on-demand build path is
  made real; result-index-deletion on removal stays consistent under
  concurrency.
- `dictionary-management`: removing a dictionary is permitted during staging,
  scanning, and full-text indexing (Remove is not disabled by the processing
  indication), and the removal is applied consistently to the in-flight build,
  the queue, and stored files/indexes within a bounded time.

## Impact

- `carve/gd_boundary.cc` — sliced build loop for `gd_fts_index` (acquire per
  slice, release between); in-flight dictionary id passed as `mutedDicts` in
  `gd_lookup`/`gd_lookup_in_group`; a real per-dictionary cancellation flag
  (currently `isCancelled` is created and never set); id-addressed removal
  ordering against an in-flight build.
- `app/EngineController.cpp` — `removeDictionary` guard, `autoIndexMissing`
  bounding/enumeration, `ftsIndex`/`ftsSearch` on-demand build trigger, FTS
  worker resume/cancel handling.
- `app/main.qml` — Remove button enablement (drop the `!processingActive`
  condition).
- `engine/src/ftshelpers.cc` — bounded/resumable build, periodic commit at slice
  boundaries, atomic publish instead of `compact()`, via `patches/` (upstream is
  never edited in place) with the CI smoke test kept green.
- `docs/ROADMAP.md` — retires the "Off-thread FTS indexing" candidate when
  archived.
- Localization: no user-visible English text changes, so no RU/JA catalog work.
