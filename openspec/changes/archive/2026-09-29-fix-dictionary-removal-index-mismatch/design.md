# Design - fix dictionary removal index mismatch

## D1 - Two index spaces, and the one the boundary uses

The engine keeps its loaded dictionaries in `g_state->dictionaries`, and every
index-taking function resolves against that vector:
`gd_dict_info`/`gd_dict_id`/`gd_dict_meta` (`carve/gd_boundary.cc:874-953`) and
`gd_remove_dict` (`:977`). The app, however, exposes a *sorted* view:
`EngineController::refreshDictionaries` builds the list in engine order and then
`std::sort`s it alphabetically by name (`app/EngineController.cpp:697-701`) so
the flat list and the By-Pair groups are alphabetical (`dictionary-management`
spec). From that point the display position and the engine index are different
numbers.

`removeDictionary(int)` treated the caller's argument as an engine index. The
QML passed the row's `index` in `engine.dictionaries`, i.e. the display
position. With the two spaces equal (few dictionaries, names in load order) the
bug is invisible; once they diverge the removal unloads a different dictionary
while deleting the *selected* dictionary's file, which is exactly the reported
"Remove does nothing / the deleted one comes back after a restart".

Rejected: sort the engine's vector to match the display list. Engine order is
user-meaningful - the "All" group's reorder sets article order
(`dictionary-management` "reorder dictionaries") - so it must not be forced to
the display sort.

Rejected: stop sorting `dictionaries()` and sort in QML. The flat and By-Pair
views both need alphabetical order, and the By-Pair grouping already re-derives
order in QML. Keeping the sort server-side and carrying the engine index is the
smaller change and keeps one definition of "what `dictionaries()` contains".

## D2 - Carry `engineIndex`, translate at the edge

Each entry gains `"engineIndex"` (the `i` the metadata was read with). All
display-facing code keeps using positions; the boundary-crossing method resolves
the position to the engine index just before calling `gd_*`. The translation
lives in the engine-index-taking removal path only; `gd_group_*` already receive
engine indices because `groupDicts` reports `m.insert("index", i)`
(`EngineController.cpp:1108`), and the FTS queue stores ids, not indices
(`autoIndexMissing`, `ensureFtsWorker`), so neither needs the new field.

`removeDictionary(int)` is kept as the single-entry entry point and delegates to
`removeDictionaries({index})`; QML's multi-select now calls the batch form. The
single method's signature is unchanged, so any other caller is unaffected.

## D3 - One ordered batch, not N concurrent tasks

The old multi-select looped and called `removeDictionary` per position, each
spawning an independent `QtConcurrent` task. `gd_remove_dict` shifts every index
above the erased one, and independent tasks can acquire `g_engineMutex` in any
order, so even with correct indices a batch could erase the wrong slot. The new
path resolves every target on the UI thread (before anything shifts), sorts by
engine index descending, and unloads them **sequentially in one worker**. Each
erase only shifts indices below the one just removed, so no later target is
invalidated. The worker returns each dictionary's id and the final count; the
UI thread then deletes files/indexes and drops the ids from the FTS queue, as
before.

Rejected: keep the per-dictionary tasks but pass a lock-ordering token. There is
no ordering primitive across independent `QtConcurrent` tasks short of a second
mutex; one task is simpler and strictly correct.

Rejected: serialize the whole batch under `g_engineMutex`. That would hold the
engine mutex across the batch and stall every other `gd_*` call; the current
design already avoids UI-thread engine work and should keep doing so.

## D4 - Header-only helper, host-testable

The mapping/order rule is pure data work with no engine dependency, so it lives
in `app/DictionaryIndex.hpp` (Qt Core only), following `app/IndexMigration.hpp`
and `app/IndexCleanup.hpp`. `app/tests/DictionaryIndexTest.cpp` pins the
behaviour: a model whose display order differs from engine order maps each
position correctly; targets are unique, ordered highest-engine-index-first, and
invalid positions are dropped. The test builds no engine code, so it runs in CI
without an Android toolchain.

## Risks

- **Stale `engineIndex` after a list mutation.** `refreshDictionaries` rebuilds
  the list from the engine on every change and resets the field, and removals
  are refused while `m_processingActive`; the field cannot outlive the list it
  describes.
- **A removal racing a scan or FTS build.** Unchanged guard: `removeDictionaries`
  returns early while `m_processingActive`, matching the disabled Remove control.
- **File deletion for a batch sharing a staged folder.** Each dictionary's own
  source file is still deleted individually; the staged directory is kept when a
  sibling remains. Removing two siblings in one batch can leave an empty staged
  directory behind (the shared check runs before the list refresh) - inert, and
  the same as the previous per-file behaviour.
