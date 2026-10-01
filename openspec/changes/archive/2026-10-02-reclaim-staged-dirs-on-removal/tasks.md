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
- [x] 1.5 Instrument the guard and remove one dictionary. **Measured answer:**
  `m_unloadedSources` is **empty** when the guard runs, because the user's
  removal path never appends to it — only the *duplicate-resolution* path does
  (`removeDuplicates`, EngineController.cpp:1174). `removeDictionaries` calls
  `deleteDictionaryFiles(...)` and only calls `refreshDictionaries()` afterwards,
  so `m_dictionaries` still lists the removed dictionary and nothing excludes it.
  The log was unambiguous:

  ```
  DIAG liveDict source: ".../70549544/stardict.ifo" excluded= false
  DIAG m_unloadedSources: QList()                       <- empty
  DIAG MATCHING SOURCE: ".../70549544/stardict.ifo"
  ```

  The paths were byte-identical, so this was **not** a string mismatch. Four
  candidate mechanisms had been considered from reading the code; **all four were
  wrong**, and one instrumented run settled it. That is the argument for 1.5
  existing at all.
- [x] 1.6 Recorded above, replacing the candidate list
- [x] 1.7 The re-import mechanism: staging overlays into the existing
  `staged/<id>`, so files already present are not re-copied and a deleted primary
  file is never restored. Confirmed by the hand-deletion experiment in 1.4, where
  removing the incomplete directory made the next import succeed.

## 2. Fix the guard

- [x] 2.1 Make the sharing guard stop counting the dictionary being removed as a
  remaining user of its staged directory — `removeDictionaries` now appends the
  removed source to `m_unloadedSources` **before** deleting files, exactly as the
  duplicate path already did
- [x] 2.2 Preserve sibling safety exactly: a directory another loaded dictionary
  still reads from must survive (host tests cover both directions)
- [x] 2.3 Keep the containment guard (direct child of the staged root) untouched

## 3. Reclaim what is already orphaned — now a repair, not tidy-up

- [x] 3.1 Extend the stale-directory sweep to reclaim a staged directory that
  holds no primary file any dictionary loads. Uses the new
  `StagingRules::isPrimaryDictionaryName` (`.mdx`/`.dsl`/`.dsl.dz`/`.ifo`),
  deliberately not `isSupportedDictionaryName`, which also accepts companions and
  so would never detect the orphan. Checked **before** the failed-import test,
  because such a directory produces no scan failure
- [x] 3.2 Confirm it cleans up the orphan already present on the test device —
  **verified**: on launch, `sweeping staged dir holding no dictionary
  ".../70549544"` then `removing staged dir`, with no user action
- [x] 3.3 Confirm it cannot reclaim a directory an in-flight staging run is
  still writing into — the sweep now returns early while `m_stagingActive`
- [x] 3.4 Confirm the sweep only reclaims a directory that holds **no** primary
  file — a directory holding a valid one is skipped (host test 4.3)

## 4. Host tests

- [x] 4.1 `StagedCleanupTest`: a directory whose only owner has just been removed
  is reclaimable — the case that failed
- [x] 4.2 `StagedCleanupTest`: a directory shared with a surviving dictionary is
  **not** reclaimable — the case the guard exists for
- [x] 4.3 `StagingRulesTest`: `isPrimaryDictionaryName` identifies `.mdx`/`.dsl`/
  `.dsl.dz`/`.ifo` and rejects the measured orphan contents (`stardict.idx`,
  `.dict.dz`, `.syn`), `.mdd`, resource images and the empty name
- [x] 4.4 Confirm all existing host tests still pass — all **8** binaries pass
- [x] 4.5 **Teeth check**: with `isPrimaryDictionaryName` forced to return false,
  6 assertions fail; restored, 0. The new coverage is not vacuous

## 5. Verify on device, across formats

- [x] 5.1 Remove a **StarDict** dictionary; confirm the staged directory and its
  `res/` tree are gone, and other dictionaries still work. **Verified**: the log
  now reads `removed staged source file ... ok= true` followed by
  `removing staged dir ".../f804830f"`, with **no** `staged dir kept` — the line
  that used to end the sequence before the fix
- [x] 5.2 **Re-import that dictionary and confirm it loads and looks up** —
  **verified**: `70549544` is staged again with `stardict.ifo` present alongside
  its `res/`, `.idx`, `.dict.dz` and `.syn`, and its index and `_FTS_x` are
  rebuilt
- [x] 5.3 Remove a **DSL** dictionary (`.dsl.dz` + `.dsl.files/`); confirm the
  same cleanup, **and** that it too can be re-imported. **Verified on device**,
  and it answers the format-general concern: `aurelex-basic.dsl.dz` (a different
  primary extension from StarDict's `.ifo`) behaves identically —
  `removed staged source file ... ok= true` then `removing staged dir`, and the
  same folder re-imports with its `.dsl.dz` present and loads. The fix is not
  StarDict-specific
- [x] 5.4 Confirm no dictionary's files were deleted while it was still loaded —
  the regression this guard exists to prevent. **Verified on device**, and this
  is the check that shows the guard still discriminates: three DSLs were staged
  in **one** folder (`AurelexTest/shared`), one was removed, and the log reads

  ```
  removed staged source file ".../d1aff614/aurelex-phrasebook.dsl" ok= true
  staged dir kept, a loaded dictionary uses it ".../d1aff614"
  staged copy dir kept (shared by siblings) ".../d1aff614"
  ```

  The directory survived holding `aurelex-basic.dsl` and `aurelex-lingvo.dsl`,
  both of which kept working. So the guard reclaims an unshared directory and
  keeps a shared one — the `staged dir kept` line is now **correct** rather than
  the bug it was in 1.2, and the two cases are distinguished by the same code
  path.

## 6. Documentation

- [x] 6.1 `docs/TESTING.md`: record the recipe for removal cleanup and re-import,
  with the measured before/after, so the symptom ("removing a dictionary stops
  it being re-addable") is searchable. Recipe **8d** already existed and was
  marked unrun — it is now verified — and **8e/8f/8g** were added for
  re-import, the shared-folder case, and the DSL check
- [x] 6.2 Note the format scope: which formats were verified, and which were not.
  Recorded in 8g: **StarDict and DSL verified on device; MDict shares the staged
  shape but its removal has not been run on device.** The fix is
  format-agnostic (`isPrimaryDictionaryName` covers all three), and the host
  tests do not distinguish formats, so the risk is low — but it is stated rather
  than implied

## Notes

Found while verifying StarDict resource staging, as a second-order effect of the
removal test in that recipe. Not part of `verify-mdx-import` (MDict) or
`stardict-bword-link-navigation` (link scheme). One session produced three
unrelated findings; each is tracked separately.

Originally filed as a disk leak of about 18 MB per removal. Task 1.4 changed
that assessment: the dictionary cannot be re-added afterwards, which breaks an
existing scenario. The index side of removal already behaves correctly and is
deliberately out of scope — this change is about the staged files.

### The measurement that mattered

Four candidate mechanisms for the guard's failure were proposed from reading the
code, and **all four were wrong**. One instrumented run settled it: the log
showed `m_unloadedSources: QList()` — empty — because only the
duplicate-resolution path populated it, not the user's Remove. Task 1.5 existed
to force that measurement, and the change would have been *wrong* without it.

### What the two device cases prove together

They discriminate on the same code path, which is why both were needed:

| Case | Log | Meaning |
| --- | --- | --- |
| Lone dictionary removed | `removing staged dir` | reclaim when nothing else uses it |
| One of three in a folder removed | `staged dir kept, a loaded dictionary uses it` | keep when a sibling still reads from it |

The `staged dir kept` line was the *bug* in 1.2 and is *correct* in 5.4. Without
the second case a fix could reclaim everything and look right until it deleted a
sibling's files.
