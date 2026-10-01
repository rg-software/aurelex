## 1. Determine the mechanism by measurement, not by reading

- [x] 1.1 Reproduce on device: remove a StarDict dictionary and inspect the
  staged directory (`.ifo` deleted; `.idx`/`.dict.dz`/`.syn`/`res/` left)
- [x] 1.2 Capture the log: guard fires with "a loaded dictionary uses it" while
  only two dictionaries remained, both in other directories
- [x] 1.3 Record that the index cleanup is **already correct** (3 → 2, both
  entries removed) so the fix is scoped to files, not indexes
- [ ] 1.4 Instrument the guard (print `primaryFile`, the compared `source`, and
  `m_unloadedSources`) in a build and remove one dictionary, to establish **why**
  it matches. Four mechanisms have been considered; three were ruled out by
  reading the code, which is why this must be measured before a fix is chosen
- [ ] 1.5 Record the measured mechanism in `design.md`, replacing the candidate
  list

## 2. Fix the guard

- [ ] 2.1 Make the sharing guard stop counting the dictionary being removed as a
  remaining user of its staged directory
- [ ] 2.2 Preserve sibling safety exactly: a directory another loaded dictionary
  still reads from must survive
- [ ] 2.3 Keep the containment guard (direct child of the staged root) untouched

## 3. Reclaim what is already orphaned

- [ ] 3.1 Extend the stale-directory sweep to reclaim a staged directory that
  holds no primary file any dictionary loads, so a directory orphaned by an
  earlier removal is released rather than accumulating
- [ ] 3.2 Confirm this cleans up the 18 MB already leaked on the test device
- [ ] 3.3 Confirm it cannot reclaim a directory an in-flight staging run is
  still writing into

## 4. Host tests

- [ ] 4.1 `StagedCleanupTest`: a directory whose only owner has just been removed
  is reclaimable — the case that failed
- [ ] 4.2 `StagedCleanupTest`: a directory shared with a surviving dictionary is
  **not** reclaimable — the case the guard exists for
- [ ] 4.3 Confirm all existing host tests still pass

## 5. Verify on device, across formats

- [ ] 5.1 Remove a **StarDict** dictionary; confirm the staged directory and its
  `res/` tree are gone, and other dictionaries still work
- [ ] 5.2 Remove a **DSL** dictionary (`.dsl.dz` + `.dsl.files/`); confirm the
  same. This tests the scope claim rather than assuming the bug is
  StarDict-only — the reporter's concern that all formats are affected
- [ ] 5.3 Re-add a removed dictionary and confirm it loads fresh with a working
  index (removal must not leave state that blocks re-import)
- [ ] 5.4 Confirm no dictionary's files were deleted while it was still loaded —
  the regression this guard exists to prevent

## 6. Documentation

- [ ] 6.1 `docs/TESTING.md`: record the recipe for removal cleanup and the
  measured before/after, so the symptom ("removing a dictionary does not free
  its space") is searchable
- [ ] 6.2 Note the format scope: which formats were verified, and which were not

## Notes

Found while verifying StarDict resource staging, as a second-order effect of the
removal test in that recipe. Not part of `verify-mdx-import` (MDict) or
`stardict-bword-link-navigation` (link scheme). One session produced three
unrelated findings; each is tracked separately.

The index side of removal already behaves correctly and is deliberately not in
scope — this change is about the staged files only.
