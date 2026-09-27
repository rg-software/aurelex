## Why

Removing a dictionary no longer deletes its index.

`EngineController::deleteDictionaryFiles` globs `appDir/index<id>*`
(`app/EngineController.cpp:763`). That was the layout before
`fix-index-directory-path-separator`, which corrected the index directory to a
prefix so the engine writes `<appDir>/index/<id>` (and
`<id>_FTS_x`). The glob does not match `index/<id>` - `index<id>` is a different
name - so the removal block is dead code and every index survives removal.

Device evidence (2026-09-28): `files/index/` held 39 btree indexes while
`groups.json` referenced 38 ids. `bedcf3169d9018133eb545df1b90c037` was an index
with no dictionary, no `_FTS_x` companion, and no entry in `allOrder` - the
leftover of a removed dictionary.

The existing spec already requires this: "Remove a loaded dictionary" says the
removal deletes "its staged files and index", and "Removal is reflected in
full-text search" says "the index is deleted". So this is a regression against a
shipped requirement, not a new one.

Two consequences:

- Storage grows without bound across remove/re-add cycles (dictionaries are
  large; a leaked index is a significant fraction of the dictionary).
- A re-added dictionary can inherit the index left behind: the engine rebuilds
  only when the index is older than the source (mtime), so a dictionary removed
  and re-imported can be served from its previous index.

A second, smaller defect in the same removal path: `gd_remove_dict` rewrites the
in-memory group set but never calls `saveGroupsLocked()`, so `groups.json` keeps
the removed dictionary's id (and `allOrder` entry) until the next scan or group
mutation rewrites it. The on-disk group set is therefore briefly inconsistent
with what the app shows.

Out of scope: the Search field's behaviour while the engine is busy indexing.
The FTS tab disables its field while `buildingFts`; the Search field does not, so
a search issued during a large FTS build blocks on the engine mutex until the
build finishes. That is a separate decision and is deferred - see design.md D4
for what to capture on the next reproduction.

## What Changes

- **Delete the index where the engine actually writes it.** The removal path
  deletes `<index dir>/<id>` and its `<id>_FTS_*` companions, and still deletes
  the pre-fix `<appDir>/index<id>*` strays for a device that has not run the
  migration. Nothing else in the index directory is touched.
- **Make the path logic testable.** The "which on-disk entries belong to this
  dictionary's index" rule moves into a header-only helper
  (`app/IndexCleanup.hpp`), the way `IndexMigration.hpp` already is, so a host
  test pins both layouts without building the engine.
- **Persist group state on removal.** `gd_remove_dict` saves the group set after
  remapping, so `groups.json` matches the in-memory set immediately.

No engine change: `engine/` stays byte-for-byte at the pinned tag, no
`patches/` entry, no upstream delta. The engine's own index naming is upstream's
documented contract (`indicesDir + dictId`), so this is boundary/app work only.

## Capabilities

### Modified Capabilities

- `dictionary-management`: "Remove a loaded dictionary" currently requires the
  index to be deleted but does not say where it lives, which is exactly how the
  glob went stale. The requirement gains the concrete guarantee that the
  dictionary's entries inside the app's index directory are deleted (alongside
  any pre-fix sibling strays), plus a scenario; and it gains the guarantee that a
  removal's effect on groups is durable across a restart.

## Impact

- Affected code:
  - `app/EngineController.cpp` - `deleteDictionaryFiles` uses the new helper
    instead of the stale glob.
  - `app/IndexCleanup.hpp` - new header-only helper (Qt Core only).
  - `app/tests/IndexCleanupTest.cpp` - new host test; `app/tests/CMakeLists.txt`
    gains a target for it.
  - `carve/gd_boundary.cc` - `gd_remove_dict` persists the group set.
- Affected APIs: none. No `gd_*` boundary function is added, removed, or
  changed; `gd_remove_dict` keeps its signature and return codes and only gains
  a save.
- Affected dependencies: none. No new engine source, no patch, no upstream bump.
- Upstream fidelity: `engine/` unchanged.
- Localization: no catalogs touched; no user-visible English text changes, so
  `scripts/update-translations.ps1` is not needed.
- On-disk effect: removing a dictionary frees its index. Existing leaked indexes
  from before the fix are not swept proactively - a leaked index is inert (no
  loaded dictionary has that id), so the fix stops new leaks and leaves old ones
  as dead bytes rather than risk deleting a live index whose dictionary merely
  failed to load.
