## Why

While a large dictionary indexes, the UI itself stays responsive — the build runs
off-thread and progress is shown — but the app is not *searchable*: `gd_fts_index`
holds the global `g_engineMutex` for the entire `makeFTSIndex()` run, so every
lookup, scan, group edit, and removal blocks until the build finishes. The
existing spec promises the user "can keep using the rest of the app"
(`full-text-search`), which is only half-true: responsive, but lookups return
nothing until indexing ends. On top of that, `makeFTSIndex` commits only once at
the very end — an interrupted build loses all work — and `compact()` rewrites the
whole index a second time. The app also disables the Dicts Remove button for the
whole processing chain, so a dictionary cannot be deleted while anything is
indexing.

## What Changes

- **FTS build no longer blocks the engine.** The global `g_engineMutex` is not
  held across `makeFTSIndex()`; lookups, scans, group edits, and dictionary
  removal proceed while a build runs (`full-text-search`,
  `dictionary-management`).
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
  without the user waiting for the batch to finish.
- **Diagnostic**: confirm from `gd_scan_dicts took %lld ms` that the
  mtime-based lookup-index cache is not silently rebuilding on every launch
  before attributing slowness to FTS.

Not in scope: pre-built desktop-generated index caches (separate proposal).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `full-text-search`: index build becomes non-blocking for the rest of the
  engine; partial build work survives interruption; automatic bulk indexing is
  bounded/deferrable for very large dictionaries and the on-demand build path is
  made real; result-index-deletion on removal stays consistent under concurrency.
- `dictionary-management`: removing a dictionary is permitted during staging,
  scanning, and full-text indexing (Remove is not disabled by the processing
  indication), and the removal is applied consistently to the in-flight build,
  the queue, and stored files/indexes.

## Impact

- `carve/gd_boundary.cc` — mutex strategy for `gd_fts_index`; a real per-dictionary
  cancellation flag (currently `isCancelled` is created and never set);
  id-addressed removal ordering against an in-flight build.
- `app/EngineController.cpp` — `removeDictionary` guard, `autoIndexMissing`
  bounding/enumeration, `ftsIndex`/`ftsSearch` on-demand build trigger, FTS
  worker resume.
- `app/main.qml` — Remove button enablement (drop the `!processingActive`
  condition).
- `engine/src/ftshelpers.cc` — periodic commit / compact cadence, via
  `patches/` (upstream is never edited in place) with the CI smoke test kept
  green.
- `docs/ROADMAP.md` — retires the "Off-thread FTS indexing" candidate when
  archived.
- Localization: no user-visible English text changes, so no RU/JA catalog work.
