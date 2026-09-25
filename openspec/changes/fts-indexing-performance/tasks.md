## 1. Diagnostic groundwork

- [ ] 1.1 Relaunch with an already-imported large dictionary and read `gd_scan_dicts took %lld ms` from logcat; record whether the lookup-index cache is being rebuilt (design D5). If it is, treat that as the primary fix and note the rescope before continuing.
- [ ] 1.2 Establish a baseline: import a large test dictionary (order 1M entries) and record scan time, FTS build time, peak memory, and whether lookups/search work during the build.

## 2. Engine patch (`patches/`, periodic commit + no compact)

- [ ] 2.1 Patch `FtsHelpers::makeFTSIndex` to `db.commit()` every `kCommitEvery` documents while keeping the final `finish_mark` document as the completion signal.
- [ ] 2.2 Replace the trailing `db.compact(final)` with `db.close()` + atomic rename of the committed `_temp` directory to `ftsIndexName()` (remove any stale final first).
- [ ] 2.3 Verify the abort path removes `_temp` and leaves the final index intact, and that a resumed run continues from the last committed document instead of restarting.
- [ ] 2.4 Add the change as a numbered patch under `patches/` and wire it into the patch series / apply script per `docs/UPSTREAM.md`.
- [ ] 2.5 Build the engine, run the CI smoke test, and keep it green.

## 3. Boundary changes (`carve/`)

- [ ] 3.1 Move the FTS progress slot out of `g_state` to a file-static guarded by `g_ftsProgressMutex`.
- [ ] 3.2 In `gd_fts_index`, take `g_engineMutex` only to snapshot the target `sptr` and state, release it before `makeFTSIndex()`, and re-take it to publish results.
- [ ] 3.3 Add a cancel token + in-flight dictionary id (under `g_ftsProgressMutex`) and expose `gd_fts_cancel(const char *dict_id)` in `carve/goldendict.h` and its implementation.
- [ ] 3.4 Add `gd_fts_build_state(const char *dict_id, int *out)` reporting idle vs building for a dictionary id.
- [ ] 3.5 Make `gd_fts_index` return a distinct cancelled result and stop the build when the token is armed.
- [ ] 3.6 Guard `gd_cleanup` (and any `g_state` teardown) to wait for an in-flight build before deleting state.
- [ ] 3.7 Rebuild the carve and re-run the smoke test.

## 4. App orchestration (`app/EngineController.cpp`)

- [ ] 4.1 In `autoIndexMissing`, read each dictionary's `size_bytes` via `gd_dict_meta` and skip auto-building dictionaries above `kAutoFtsMaxBytes`, recording them as deferred.
- [ ] 4.2 In `ftsSearch`, detect scoped dictionaries that lack an index, enqueue on-demand builds on the existing single FTS worker, return results from indexed dictionaries immediately, and re-run the pending query when an on-demand build completes.
- [ ] 4.3 In `removeDictionary`, drop the `processingActive` guard; remove the id from the FTS queue and call `gd_fts_cancel(id)` before `gd_remove_dict`.
- [ ] 4.4 Gate `deleteDictionaryFiles` on the engine reporting the removed dictionary's build idle (bounded wait), otherwise defer deletion to the FTS worker's completion callback.
- [ ] 4.5 Make the FTS worker count a cancelled build, continue with the next queued dictionary, and keep overall progress/notification correct when a dictionary is removed mid-batch.

## 5. QML (`app/main.qml`)

- [ ] 5.1 Remove the `!engine.processingActive` condition from the Dicts Remove button's `enabled` and `highlighted` (keep the selection condition).
- [ ] 5.2 Check other removal entry points and confirms for any remaining `processingActive` gating of deletion.

## 6. Verification

- [ ] 6.1 On-device: while a large dictionary builds, confirm ordinary lookups and full-text searches over already-indexed dictionaries still return results.
- [ ] 6.2 On-device: remove a dictionary during its own FTS build; confirm it disappears immediately, its staged files and index are gone, and other dictionaries keep indexing.
- [ ] 6.3 On-device: kill the app mid-build, relaunch, and confirm the build resumes rather than restarting; confirm peak memory stays bounded.
- [ ] 6.4 On-device: import a dictionary above the bound, confirm the import chain does not build it, then run a full-text search and confirm it builds and its results appear on completion.
- [ ] 6.5 Update `docs/TESTING.md` rows for the changed behavior; retire the "Off-thread FTS indexing" candidate in `docs/ROADMAP.md` at archive time.
- [ ] 6.6 Confirm no user-visible English string changed; if any did, run `scripts/update-translations.ps1` and update RU/JA catalogs + `.qm` in the same change.
