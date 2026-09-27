## 1. Root cause

- [x] 1.1 Confirm `deleteDictionaryFiles` globs `appDir/index<id>*` while the engine writes `<appDir>/index/<id>` after `fix-index-directory-path-separator`, so the loop matches nothing
- [x] 1.2 Confirm on device that a leaked index exists: `files/index/` had 39 btree indexes vs 38 ids in `groups.json`, with `bedcf3169d9018133eb545df1b90c037` referenced by neither `allOrder` nor any group
- [x] 1.3 Confirm `gd_remove_dict` remaps `groupDefs` and rebuilds but never calls `saveGroupsLocked()`, unlike every other group mutation

## 2. Index cleanup helper (app/IndexCleanup.hpp)

- [x] 2.1 Add a header-only `IndexCleanup::removeIndexEntries(appDir, dictId)` (Qt Core only) that deletes `<appDir>/index/<id>*` (the engine's current layout; the id is 32 hex chars, so the prefix cannot match another dictionary) and returns the removed paths
- [x] 2.2 Delete recursively when the entry is a directory (`<id>_FTS_x`) and by `QFile::remove` when it is a file (the btree index)
- [x] 2.3 Also delete the pre-fix `<appDir>/index<id>*` strays, so a removal is correct even if `IndexMigration` has not run or a rename failed (design D2)
- [x] 2.4 Leave everything else in the index directory alone (other dictionaries' indexes; an unrelated `index.txt`)

## 3. Wire it into the removal path

- [x] 3.1 Replace the stale glob block in `EngineController::deleteDictionaryFiles` with a call to the helper, keeping the per-entry `qInfo` log line
- [x] 3.2 Confirm the staged-file and staged-dir deletion below it is unchanged and still runs when the index delete finds nothing

## 4. Persist group state on removal

- [x] 4.1 Call `saveGroupsLocked()` at the end of `gd_remove_dict`, after `rebuildGroups()`, so `groups.json` matches the in-memory set immediately (design D5)

## 5. Tests

- [x] 5.1 Add `app/tests/IndexCleanupTest.cpp` covering: current layout (`index/<id>` + `index/<id>_FTS_x/...` deleted, a second id untouched), pre-fix layout (`index<id>` + `index<id>_FTS_x/...` deleted), unrelated names untouched, and the empty/absent case
- [x] 5.2 Add an `index_cleanup_test` target to `app/tests/CMakeLists.txt` (Qt Core only)
- [x] 5.3 Build and run the host test; confirm the current-layout scenario contradicts the old glob by construction (the old `appDir/index<id>*` matches nothing under `index/`, so its "removed three entries" assertion would fail) and passes with the helper
- [x] 5.4 Re-run the engine smoke (`aurelex_smoke`) to confirm the boundary change did not disturb it

## 6. On-device verification

- [ ] 6.1 Remove a dictionary and confirm its `files/index/<id>` and `files/index/<id>_FTS_x` are gone, while the other dictionaries' indexes remain
- [ ] 6.2 Re-import a removed dictionary and confirm the lookup renders from a freshly built index (not a stale one), and the FTS tab finds a term from the new content
- [ ] 6.3 Confirm `groups.json` no longer lists the removed dictionary immediately after a removal
- [ ] 6.4 Capture logcat (tag `aurelex`) on the next "search field does nothing" reproduction and record whether `suggest firing` is followed by a long `suggest ready` / `gd_suggest ... mutex=NNNms` while `fts progress` is advancing (design D4) - this decides a follow-up change, not this one
