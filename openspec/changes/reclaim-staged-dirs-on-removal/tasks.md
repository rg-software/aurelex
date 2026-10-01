## 1. Determine the mechanism by measurement, not by reading

- [x] 1.1 Reproduce on device: remove a StarDict dictionary and inspect the
  staged directory (`.ifo` deleted; `.idx`/`.dict.dz`/`.syn`/`res/` left)
- [x] 1.2 Capture the log: guard fires with "a loaded dictionary uses it" while
  only two dictionaries remained, both in other directories
- [x] 1.3 Record that the index cleanup is **already correct** (3 → 2, both
  entries removed) so the fix is scoped to files, not indexes
- [x] 1.4 **Establish the user-visible consequence, which raises this from a
  leak to a defect**: re-adding the removed dictionary **fails**. Confirmed on
  device — the leftover holds `.idx`/`.dict.dz`/`.syn`/`res/` but not the `.ifo`,
  and staging's dedup step does not re-copy files already present, so the
  directory never regains the primary file the dictionary is identified by.
  Deleting the orphan by hand made the re-import succeed immediately. This makes
  the existing "Re-add after removal" scenario **failing**, not merely a
  housekeeping gap
- [ ] 1.5 Instrument the guard (print `primaryFile`, the compared `source`, and
  `m_unloadedSources`) in a build and remove one dictionary, to establish **why**
  it matches. Four mechanisms have been considered; three were ruled out by
  reading the code, which is why this must be measured before a fix is chosen
- [ ] 1.6 Record the measured mechanism in `design.md`, replacing the candidate
  list
- [ ] 1.7 Confirm the re-import mechanism precisely: determine whether staging
  skips the missing primary file because of the dedup path, or whether it never
  attempts the re-copy at all. 1.4 establishes *that* it fails; this pins *how*,
  so the fix addresses the cause rather than the symptom

## 2. Fix the guard

- [ ] 2.1 Make the sharing guard stop counting the dictionary being removed as a
  remaining user of its staged directory
- [ ] 2.2 Preserve sibling safety exactly: a directory another loaded dictionary
  still reads from must survive
- [ ] 2.3 Keep the containment guard (direct child of the staged root) untouched

## 3. Reclaim what is already orphaned — now a repair, not tidy-up

- [ ] 3.1 Extend the stale-directory sweep to reclaim a staged directory that
  holds no primary file any dictionary loads. This is what unblocks re-import for
  a user whose removal already left one, so it carries the user-visible fix
  rather than only reclaiming space
- [ ] 3.2 Confirm this cleans up the orphan already present on the test device
- [ ] 3.3 Confirm it cannot reclaim a directory an in-flight staging run is
  still writing into
- [ ] 3.4 Confirm the sweep only reclaims a directory that holds **no** primary
  file — a directory holding a valid one belongs to a dictionary and must not be
  touched

## 4. Host tests

- [ ] 4.1 `StagedCleanupTest`: a directory whose only owner has just been removed
  is reclaimable — the case that failed
- [ ] 4.2 `StagedCleanupTest`: a directory shared with a surviving dictionary is
  **not** reclaimable — the case the guard exists for
- [ ] 4.3 `StagedCleanupTest`: a directory holding a valid primary file is not
  reclaimable even when no dictionary is currently loaded for it
- [ ] 4.4 Confirm all existing host tests still pass

## 5. Verify on device, across formats

- [ ] 5.1 Remove a **StarDict** dictionary; confirm the staged directory and its
  `res/` tree are gone, and other dictionaries still work
- [ ] 5.2 **Re-import that dictionary and confirm it loads and looks up** — the
  behaviour that is broken today, and the point of this change
- [ ] 5.3 Remove a **DSL** dictionary (`.dsl.dz` + `.dsl.files/`); confirm the
  same cleanup, **and** that it too can be re-imported. This tests the scope
  claim rather than assuming the bug is StarDict-only — the reporter's concern
  that all formats are affected
- [ ] 5.4 Confirm no dictionary's files were deleted while it was still loaded —
  the regression this guard exists to prevent

## 6. Documentation

- [ ] 6.1 `docs/TESTING.md`: record the recipe for removal cleanup and re-import,
  with the measured before/after, so the symptom ("removing a dictionary stops
  it being re-addable") is searchable
- [ ] 6.2 Note the format scope: which formats were verified, and which were not

## Notes

Found while verifying StarDict resource staging, as a second-order effect of the
removal test in that recipe. Not part of `verify-mdx-import` (MDict) or
`stardict-bword-link-navigation` (link scheme). One session produced three
unrelated findings; each is tracked separately.

Originally filed as a disk leak of about 18 MB per removal. Task 1.4 changed
that assessment: the dictionary cannot be re-added afterwards, which breaks an
existing scenario. The index side of removal already behaves correctly and is
deliberately out of scope — this change is about the staged files.
