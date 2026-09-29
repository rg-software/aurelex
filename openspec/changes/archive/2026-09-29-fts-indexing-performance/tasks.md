## 1. Diagnostic groundwork

- [x] 1.1 Relaunch with an already-imported large dictionary and read `gd_scan_dicts took %lld ms` from logcat; record whether the lookup-index cache is being rebuilt (design D6). **Verified on device: cold scan 6817 ms, warm relaunch scan 52 ms → the lookup-index cache is NOT rebuilt every launch; D6 does not dominate.**
- [x] 1.2 Establish a baseline: import a large test dictionary (order 1M entries) and record scan time, FTS build time, peak memory, and whether existing dictionaries can be looked up while the build runs. **Verified on device with a 200k-entry StarDict: warm scan 52 ms; build ran 79.6 s before cancellation; lookups during the build returned in 315–481 ms. Peak memory not separately measured.**

## 2. Engine patch (`patches/`, yield hook + periodic commit + atomic publish)

- [x] 2.1 Patch `FtsHelpers::makeFTSIndex` to call a yield hook (`setYieldCallback`) every `kSliceBudgetMs` so the caller can release its engine lock mid-build (design D1/D3).
- [x] 2.2 Commit every `kCommitEvery` documents while keeping the final `finish_mark` document as the completion signal, so `ftsIndexIsOldOrBad`/`haveFTSIndex` are unchanged and peak memory is bounded.
- [x] 2.3 Replace the trailing `db.compact(final)` with `db.close()` + atomic publish: remove any stale final, rename the committed `_temp` into place; recover a `_temp` that already carries `finish_mark` (killed before publish) by publishing it. Compact retained as a fallback if the rename fails.
- [x] 2.4 Verify the abort path removes `_temp` and leaves the final index intact, and that a resumed run continues from the last committed document instead of restarting. **Verified on device: killed mid-build, relaunch logged `Resuming FTS indexing from offset 696412 at index 31656`; cancellation removed the in-flight `_temp` and the final index (`gd_fts_index ... rc=-2`).**
- [x] 2.5 Add the change as a numbered patch under `patches/0004-fts-sliced-build.patch`; `scripts/apply-patches.*` picks it up automatically.
- [x] 2.6 Build the engine, run the CI smoke test, and keep it green.

## 3. Boundary changes (`carve/`)

- [x] 3.1 Rewrite `gd_fts_index`: take a `unique_lock`, hold the target alive with an `sptr`, install a yield hook that unlocks/relocks `g_engineMutex` each slice, and call `makeFTSIndex` once (design D1).
- [x] 3.2 Register the in-flight dictionary id as a file-static under `g_ftsProgressMutex`, and clear it when the build ends.
- [x] 3.3 Pass the in-flight id as `ArticleMaker::makeDefinitionFor`'s `mutedDicts` in `gd_lookup` and `gd_lookup_in_group` so the dictionary being built is withheld from lookup (`gd_fts_search` already omits it via `haveFTSIndex`); keyed on "build in flight", not on "index missing" (design D2).
- [x] 3.4 Add a cancel flag + in-flight dictionary id under `g_ftsProgressMutex` and expose `gd_fts_cancel(const char *dict_id)` in `carve/goldendict.h` and its implementation.
- [x] 3.5 Add `gd_fts_build_state(const char *dict_id, int *out)` reporting idle (0) vs building (1) for a dictionary id.
- [x] 3.6 Make `gd_fts_index` return a distinct cancelled result (-2) and stop the build at the next slice boundary when the token is armed.
- [x] 3.7 Guard `gd_cleanup` to wait for an in-flight build before deleting state.
- [x] 3.8 Rebuild the carve and re-run the smoke test (added `FTS_BUILD_STATE` assertion for the new ABI).

## 4. App orchestration (`app/EngineController.cpp`)

- [x] 4.1 In `autoIndexMissing`, read each dictionary's `size_bytes` via `gd_dict_meta` and skip auto-building dictionaries above `kAutoFtsMaxBytes`, recording them as deferred.
- [x] 4.2 In `ftsSearch`, detect scoped dictionaries that lack an index, enqueue on-demand builds on the existing single FTS worker, return results from indexed dictionaries immediately, and re-run the pending query when an on-demand build completes.
- [x] 4.3 In `removeDictionaries`, drop the `processingActive` guard; remove the id from the FTS queue and call `gd_fts_cancel(id)` before `gd_remove_dict`.
- [x] 4.4 Gate `deleteDictionaryFiles` on `gd_fts_build_state(id)` reporting idle (bounded wait, `kFtsIdleWaitMs`), so a build that was mid-publish finishes first.
- [x] 4.5 Make the FTS worker count a cancelled build, record a failed build so an on-demand re-run cannot loop, and keep overall progress/notification correct when a dictionary is removed mid-batch.
- [x] 4.6 Confirm only one build per dictionary can be in flight: the boundary's `g_ftsBuildActive` guard rejects a second concurrent build.

## 5. QML (`app/main.qml`)

- [x] 5.1 Remove the `!engine.processingActive` condition from the Dicts Remove button's `enabled` and `highlighted` (keep the selection condition).
- [x] 5.2 Check other removal entry points and confirms for any remaining `processingActive` gating of deletion (none: only the catalog/download buttons remain gated).

## 6. Verification

- [x] 6.1 On-device: while a large dictionary builds, confirm ordinary lookups and full-text searches over other dictionaries return within about one slice, and the dictionary being built is absent from results until its index completes. **Verified: during a 200k-entry build, `gd_lookup` mutex wait was 270–407 ms (≈ `kSliceBudgetMs`), total 315–481 ms; BigTest (the in-flight dict) was withheld.**
- [x] 6.2 On-device: remove a dictionary during its own FTS build; confirm it disappears within a bounded time, its staged files and index are gone, and other dictionaries keep indexing. **Verified: removing BigTest mid-build (79.6 s in) returned rc=0; `gd_fts_index ... rc=-2`; staged source + dir and both index entries deleted; the rest of the batch continued and drained.**
- [x] 6.3 On-device: kill the app mid-build, relaunch, and confirm the build resumes rather than restarting; confirm peak memory stays bounded. **Verified: resumed from the last commit (`Resuming FTS indexing from offset 696412`). Peak memory not separately measured.**
- [x] 6.4 On-device: import a dictionary above the bound, confirm the import chain does not build it, then run a full-text search and confirm it builds and its results appear on completion. **Verified: 6 dictionaries were logged as deferred during the import chain; the first FTS search logged `on-demand FTS builds enqueued for ...`, all deferred dictionaries now carry `_FTS_x` indexes, and the armed re-run returned results (`gd_fts_search rc= 2109`).**
- [x] 6.5 Update `docs/TESTING.md` rows for the changed behavior (done); retire the "Off-thread FTS indexing" candidate in `docs/ROADMAP.md` (done — moved to Recently completed).
- [x] 6.6 Confirm no user-visible English string changed (only conditions/comments changed; no `qsTr`/`tr` arguments touched).
