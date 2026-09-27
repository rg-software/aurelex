# Design - fix dictionary removal cleanup

## D1 - Delete the index where the engine writes it, and only that

A dictionary's indexes are named `<index dir><dictId>` and
`<index dir><dictId>_FTS_x` by the engine's backends (`engine/src/dict/dsl.cc:1752`
and 17 siblings; the `index dir` is a prefix, not a directory - see
`carve/index_path.hpp`). `EngineController::initialize` sets the prefix to
`<appDir>/index/` (`app/EngineController.cpp:593`), so the entries to delete are
`<appDir>/index/<id>` and `<appDir>/index/<id>_FTS_*`.

The removal deletes entries by **name prefix `<id>` inside the index directory**
rather than by an exact list. The engine may leave a third name, `<id>_FTS_x_temp`
(the transient build directory), and a prefix match removes it too; enumerating
exact names would silently leave it behind and it would then be inherited by a
re-add. The id is 32 fixed hex chars, so `<id>*` cannot match another
dictionary's index.

Rejected: deleting the whole index directory on any removal. One removal must not
destroy the other dictionaries' indexes.

Rejected: leaving leaked indexes and reclaiming them lazily. There is no cheap,
safe way to know an index is orphaned - a dictionary can legitimately fail to
load on one scan and load on the next, so a "no loaded dictionary has this id"
sweep could delete a live index. Inert leaked bytes are the lesser evil, and D1
stops new leaks at the source.

## D2 - Also delete the pre-fix sibling strays

A device that has not run `IndexMigration::migrateStrayIndexes` still has
`<appDir>/index<id>` (see `fix-index-directory-path-separator`). The migration
runs on every launch before `gd_init`, so by the time a removal can happen the
strays are gone - but the migration can fail (a rename error leaves the source
for a later attempt, by design), and a removal must not then leave the index
behind. The cleanup keeps the old `index<id>*` glob as well. It is cheap and it
makes the fix correct regardless of migration state.

The two patterns are disjoint: `index<id>` cannot match inside `index/` and
`<id>` cannot match beside it, so nothing is double-counted.

## D3 - Header-only helper, host-testable

The rule "these on-disk entries belong to dictionary X's index" is the part that
went wrong, and it is pure path work with no engine dependency. It moves into
`app/IndexCleanup.hpp` as a free function, following the existing
`app/IndexMigration.hpp` pattern: header-only, Qt Core only, exercised by a host
test that builds no engine code (`app/tests/IndexMigrationTest.cpp` is the
model).

`EngineController::deleteDictionaryFiles` calls it and logs each removed path, so
the app-side behaviour is unchanged apart from which files it finds.

The helper returns the removed paths rather than logging, so the test can assert
on the set and the caller keeps the log line. Deletion is directory-aware: an
entry is removed recursively when it is a directory (the `_FTS_x` index is a
directory, the btree index is a file).

## D4 - Deferred: the Search field while the engine indexes

The FTS tab disables its input and button while `engine.buildingFts`
(`app/main.qml:2598`, `:2616`); the Search field has no equivalent guard
(`app/main.qml:862`). `gd_suggest`/`gd_lookup` take `g_engineMutex`, which
`gd_fts_index` holds for a whole dictionary build, so a search issued while a
large dictionary is being indexed blocks until the build finishes. That matches
the reported "typing s does nothing / got stuck".

This is left unchanged here deliberately: it is a UX decision (disable the field
vs. keep it responsive with empty suggestions vs. chunk the build) and the
reproduction is not yet confirmed. To confirm it on the next attempt, capture
logcat tagged `aurelex` and look for:

- `[aurelex] suggest firing: "s"` with no matching `suggest ready` for a long
  time (the app only logs `suggest ready` when it takes >= 20 ms;
  `EngineController.cpp:1539`);
- `gd_suggest word=... mutex=NNNms` from the boundary's slow-call log
  (`gdLogCall`, `carve/gd_boundary.cc`), where a large `mutex` names the wait;
- `[aurelex] fts progress N / 38` lines still advancing at the same time - the
  batch holding the mutex.

If that is what the log shows, the fix belongs in a separate change.

## D5 - Persist the group set on removal

`gd_remove_dict` remaps `groupDefs[i].dictIndices` and calls `rebuildGroups()`,
but not `saveGroupsLocked()`. Every other group mutation saves; removal was the
one path that did not. The in-memory state is correct, and a later scan heals
the file (`loadGroupsLocked` re-resolves ids and drops the removed one), so the
impact is a brief on-disk inconsistency, not a wrong group. Saving is one call,
makes the file match the app immediately, and removes a class of "the file and
the UI disagree if the app dies here".

Rejected: relying on the scan to heal. It works, but it means `groups.json` is
wrong for an unbounded window (until the next scan), and the spec requires group
state to be durable.

## Risks

- **Deleting a live index.** Only entries named `<id>*` inside the index
  directory are touched, and the id is the one the engine just reported for the
  dictionary being removed. No other dictionary's entries match.
- **Double-delete across the two layouts.** The patterns are disjoint (D2).
- **A removal racing a scan.** The app already refuses removals while
  `m_processingActive` (`EngineController.cpp:702`), and every `gd_*` call
  serializes on `g_engineMutex`, so the delete cannot interleave with a scan that
  would recreate the index.
