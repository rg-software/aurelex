# Design - fix dictionary re-import reload

## D1 - Detect "the file was replaced" with a source stamp

The dictionary id is an MD5 over the source **paths**
(`Dictionary::makeDictionaryId`, `engine/src/dict/dictionary.cc:562`), so a
re-import into the same folder with the same file name produces the **same id**
with different content. That is why the existing dedup (by id) cannot tell
"already loaded" from "replaced", and why the scan discarded the new object.

A stamp of each source file's size + mtime, taken when the dictionary is loaded,
is the missing signal. `gd_scan_dicts` compares the live files against the stamps
and drops any dictionary that no longer matches. This lives in the boundary's
`EngineState` and is in-memory only: a fresh process has no loaded dictionaries,
so its first scan loads everything and stamps it then.

Size + mtime is the same heuristic the staging service already uses to decide
whether to re-copy a file (`AurelexActivity.stageTreeInto`), so the two layers
agree on what "changed" means. It can in principle miss a same-size,
same-mtime rewrite; hashing every source on every scan would cost far more than
the failure it prevents, and the staging layer would not have copied such a file
either.

## D2 - Drop the stale entry *before* the dedup, not after

The defect is the ordering: the backend factory runs before the id is checked. Two
ways to fix it:

- **Skip the factory when a dictionary with that primary path is already loaded.**
  Cheap, but it only stops the index rewrite; the update still would not take
  effect until a restart, because the old object is kept. It also cannot see an
  id change (e.g. an added `.mdd`), which is a separate overlap.
- **Drop the changed entry first, then let the normal scan rebuild it.** The
  newly built object is the one that is kept, so it reads the index that was just
  written - and the updated content is what the user gets.

Chosen: drop first. It fixes both the wedge and the "update does not take effect"
half, and it keeps the existing "the new object is built by the backend" path
rather than adding a second one.

Consequences handled:

- The reloaded dictionary is a new object, so `haveFTSIndex()` is false and the
  app's existing `autoIndexMissing` path rebuilds its full-text index. Unchanged
  dictionaries keep their state, so there is no re-validation storm on every
  import (which a "replace every object every scan" approach would cause).
- Indices shift because the dropped entry is erased and the reload appended.
  Groups are stored by id and re-resolved by `loadGroupsLocked`, and `allOrder` is
  id-based, so both follow. The app refreshes its dictionary list after every
  scan.
- The dropped object is only released once `rebuildGroups()` replaces the
  `ArticleMaker` that held a reference; that happens later in the same
  `gd_scan_dicts`, under `g_engineMutex`, so no lookup can observe the gap.
- `gd_scan_dicts` reports a reload as one new dictionary (the count is taken after
  the drop), which is what `runScan`'s refresh condition already expects.

## D3 - The regression guard must be platform-independent

The device failure is a live reader over a rewritten index. On Windows the index
file is locked while open, so the backend cannot rewrite it under the reader and
the smoke would **not** reproduce the corruption there - a test that only looked
for "Error reading from the file" would pass on CI and be worthless.

The guard therefore asserts the observable contract instead of the platform
artifact:

- `REIMPORT_RELOAD` - the scan reports the changed dictionary as newly loaded
  (pre-fix it reports 0, because the id is deduped).
- `REIMPORT_CONTENT` - a headword appended to the fixture resolves after the
  rescan (pre-fix the old object holds the old content and it is absent).
- `REIMPORT_SUGGEST` - prefix search finds the appended headword (the Search-field
  path; pre-fix, when the index is corrupted, `WordFinder` never finishes).

Verified both ways: with the drop disabled all three print FAIL and the tool exits
1; with it enabled all three print OK and it exits 0.

## D4 - Not fixed here

The `prefixMatch`-never-finishes behaviour itself is upstream (`WordFinder` has no
per-dictionary read-error completion path), and `gd_suggest` only escapes it via
its 10 s loop bound. That is what turns a corrupt index into a wedged search
instead of a failed suggestion. It is a consequence, not the cause, and the cause
is removed here; making `gd_suggest` fail fast on a read error would be a separate
change, and would need an upstream signal the boundary does not currently get.

## Risks

- **Dropping a dictionary that did not change.** The comparison is exact
  size + mtime per source file, all of them; a false positive only causes a
  rebuild (correct, if slower). A false negative (same size and mtime) leaves the
  pre-existing behaviour, which now is at least not a rewrite-under-reader,
  because the factory would not rebuild a fresh index either.
- **Reload cost.** A changed dictionary is re-parsed and re-indexed - the same
  work a restart would do. Unchanged dictionaries are unaffected, so a normal
  startup scan is unchanged.
- **FTS queue staleness.** The FTS worker resolves ids to indices at pop time and
  the reload keeps the id, so a queued id still lands on the right dictionary.
