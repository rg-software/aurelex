## Why

`sweepStaleStagedDirs()` runs after every scan — including the startup scan — and deletes a staged import directory with no prompt, no confirmation and no undo. It decides "this directory holds no dictionary" by looking for a primary dictionary file **only at the directory's top level**, while both the importer and the engine scan recursively. An import whose dictionaries live in subfolders is therefore classified as an orphan and erased on the next launch, even though those dictionaries loaded successfully minutes earlier.

That breaks two shipped requirements: `dictionary-management` §"Dictionaries in nested subfolders load", and `storage-folder-access` §"App restarts after an import". A second defect makes it worse: the sweep's "is this directory in use?" guard reads a UI model that is still empty on the first scan after launch, so at startup — precisely when the sweep is most dangerous — the guard protects nothing.

A user reporting "the Play update wiped my dictionaries" is exactly what this produces: the first launch of the new build is the first time the sweep runs, so a staged import that had been serving the user for months is classified as an orphan and erased. **No load failure is involved** — the sweep fired on the nested layout alone. The staged copies are the only copy the app owns; re-importing means finding the originals again.

## What Changes

- **The orphan test follows the recursive scan.** A staged directory is treated as holding a dictionary when *any* supported primary file exists anywhere beneath it, not only at its top level. A nested import is never mistaken for an orphan.
- **The in-use guard is derived from the engine, not from a UI model that may not be populated yet.** The sweep is given the set of source paths the engine actually loaded for the scan it is deciding about, so the guard is meaningful on the first scan after launch instead of vacuously empty.
- **No deletion without positive evidence.** A directory is reclaimed only when the scan positively established that nothing in it loads. Because the in-use guard becomes meaningful, that now holds for *every* route to `removeRecursively()` — a directory holding a loadable dictionary is no longer deletable through any branch.
- **The decision becomes host-testable.** The orphan test moves out of `EngineController.cpp` into a header beside `StagedCleanup.hpp`/`StagingRules.hpp`, so a nested-import directory is covered by a test rather than by inspection.

Not in scope: the sweep's *reported-failure* branch. It did not fire in the reported incident — that update produced no new load errors — and the loss is fully explained without it. That branch is a separate defect (its evidence is per-file, its effect is per-directory) and its fix belongs to the open `report-import-results` change, which already proposes the file-set granularity it would need. This change makes it harmless rather than rewriting it, and deliberately does not widen or narrow it. See design.md "Open Questions".

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: §"A leftover staged directory holding no dictionary is reclaimable" requires reclaiming a directory that holds no primary file **any dictionary loads**; the implementation approximates this with a top-level-only check and so reclaims directories holding live nested dictionaries. §"Dictionaries in nested subfolders load" is violated for the same reason. (§"Failures are not cleaned up without the user asking" is *also* violated today by the reported-failure branch — noted here so the gap is not lost, and deliberately left for `report-import-results`.)
- `storage-folder-access`: §"Nested subfolders in an import" and §"App restarts after an import" — a nested import currently stops surviving a restart, because the restart's startup scan reclaims its staged directory.

## Impact

- `app/EngineController.cpp` — `sweepStaleStagedDirs()` and its two call sites in `runScan()`; `liveDictionarySources()` / `removeStagedDirIfUnused()`.
- `app/StagedCleanup.hpp` — gains the recursive orphan test, so the delete decision sits next to the existing containment/sharing guards and is shared by every caller.
- `app/tests/StagedCleanupTest.cpp` — new cases for a nested import, a top-level-only import, and a directory that is genuinely empty.
- No user-visible feature changes and no new UI. No carve, boundary or engine change, so this is app-side only and needs no patch pipeline or CI smoke work.
- Behaviour change worth calling out in release notes: a staged directory that a *nested* import owns will no longer be reclaimed. A genuinely empty leftover directory is still reclaimed, so disk usage on the existing path is unaffected.

### Release note

> **Fixed:** an app update could silently erase imported dictionaries whose files live in
> subfolders of the picked folder. The dictionaries were still listed and searchable for one
> session after the update, then disappeared on the following launch. The staged cleanup
> sweep decided a directory held no dictionary by looking only at its top level, while both
> the importer and the engine scan recursively — so a nested import was mistaken for an
> empty leftover and deleted.
>
> **This fix does not restore dictionaries already lost to it.** The staged copy was the
> only copy the app owned, so there was nothing to recover from: re-import the original
> folder from your device storage and the dictionaries come back (full-text indexes rebuild
> automatically). Until then, avoid importing a folder whose dictionary files are in
> subfolders — with the affected build installed, such an import will be deleted again on the
> next app launch.
>
> Also fixed: the sweep's "in use" check read the dictionary list before that list was
> populated, so on the first scan after every launch it could not tell a live import from an
> orphan at all.