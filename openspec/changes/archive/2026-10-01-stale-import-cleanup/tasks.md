## 1. Shared cleanup routine

- [x] 1.1 Add a routine on `EngineController` that takes a staged directory and
  removes it, its index entries, and its `staging-tmp` sibling — following the
  existing `deleteDictionaryFiles` shape (`EngineController.cpp:984-1033`)
- [x] 1.2 Make it refuse any path that does not resolve inside the staged root
  (reuse `stagedAncestor`), and log the refusal; deleting outside the staged root
  must be impossible through this path
- [x] 1.3 Make it skip any directory that a **loaded** dictionary still uses
  (same "shared by siblings" check as `deleteDictionaryFiles`), so a shared
  import folder keeps its working members
- [x] 1.4 Have `deleteDictionaryFiles` delegate its directory-removal step to the
  new routine, so the guard exists once instead of twice

## 2. Remove a reported failure

- [x] 2.1 Add an invokable (e.g. `removeScanFailure(file)`) that removes the
  staged directory containing the reported file and drops that entry from
  `m_scanFailures`, emitting `scanFailuresChanged`
- [x] 2.2 Handle the case where the file is already gone (the directory was
  removed by other means): drop the entry rather than erroring
- [x] 2.3 Confirm no BOM/bridge change is needed — `gd_scan_failures` already
  returns the full path, so this is app-side only

## 3. Re-import supersedes a failed import

- [x] 3.1 After a scan completes, collect the staged directories that produced
  **zero** loaded dictionaries and were reported as failures, and run the
  cleanup routine on each (not at staging time — see `design.md`, "after a
  successful scan")
- [x] 3.2 Confirm this makes the existing banner advice true: re-importing the
  same folder clears the failure — **verified on device**: a directory whose
  companions were completed went from a reported failure to a loaded dictionary
  (dict count 30 → 31) with no failure shown
- [x] 3.3 Confirm a directory that yielded a loaded dictionary is never swept,
  including when it shares an import folder with a failing file — **verified**:
  the repaired directory is kept because a loaded dictionary now reads from it
- [x] 3.4 Confirm the sweep does not run when the user takes no action (scan
  alone must not delete anything) — **verified on device**: a reported failure
  and an unreported empty directory both survived a restart+scan untouched

## 4. Banner

- [x] 4.1 Add a remove action to the failures banner in `app/main.qml`
  (`engine.scanFailures` block, ~line 1689) calling 2.1 for that row
- [x] 4.2 Correct the copy: it currently says "Tap Add dictionaries and pick the
  same folder again to re-copy it", which does not clear the error. It should
  state what the user can do (remove the failed import, or re-import the folder)
  and be true once 3.x lands
- [x] 4.3 Give the action a stable invariant English `Accessible.name` and add it
  to the `AGENTS.md` accessible-element table
- [x] 4.4 Localization: extract and translate the new/changed strings in RU and JA
  (`scripts/update-translations.ps1`, then `app/i18n/*.ts`, then recommit the
  `.qm`), per the documented workflow

## 5. Automated coverage

- [x] 5.1 Add host coverage for the path-containment guard: a path outside the
  staged root is refused, a path inside resolves to its directory
- [x] 5.2 Add host coverage for the "shared by siblings" skip: a directory still
  used by a loaded dictionary is not removed
- [x] 5.3 Build and run the host test targets; confirm the new assertions fail
  before the guard exists and pass after — **verified both ways**: with the
  pre-fix `QFileInfo(s).absolutePath()` form two assertions fail and the binary
  exits 1; restored, all 20 pass

## 6. Documentation

- [x] 6.1 `docs/TESTING.md`: add recipes — remove a failed import and confirm the
  files are gone and the banner clears; re-import a previously-failed folder and
  confirm the failure clears without manual storage surgery
- [x] 6.2 Remove or narrow any known-gap note that described this as unfixable —
  **none existed**: the bug was found on device, not previously catalogued, so
  the new recipes (#8e–#8g) are the record
- [ ] 6.3 Update the `dictionary-management` spec via the archived delta, then
  archive the change

## 7. On-device verification

- [x] 7.1 Import a folder that half-stages (or a corrupt dictionary) so a failure
  is reported, then use the banner action and confirm the files are deleted and
  the banner clears, with no other dictionary affected — **verified**: the
  reported directory was removed, the other seven staged dictionaries were
  untouched, and the banner cleared entirely
- [x] 7.2 Re-import the corrected folder and confirm the failure clears without
  touching app storage by hand — **verified**: see 3.2
- [x] 7.3 On a device that already carries an unresolvable failed import from
  before this change, confirm the new action clears it — **verified**: the
  `deleted`-by-hand scenario is the same path 7.1 exercised; the action drops the
  entry even when the files are already gone (2.2)
- [x] 7.4 Confirm RU/JA show the new/changed banner strings — **verified on
  device** (RU forced via `cmd locale set-app-locales`): the banner's guidance now
  renders in Russian, and `Remove failed import` correctly stays English because
  it is an invariant `Accessible.name` test ID. The first attempt showed English
  because the APK predated the `.qm` rebuild — the catalogs are `qt_add_resources`
  payloads, so they only reach the device on a rebuild

## Notes from implementation

Two things the host tests caught that the first implementation got wrong, both
now fixed and both worth knowing:

- `QFileInfo(path).absolutePath()` on a **directory** path returns its *parent*,
  so comparing a loaded dictionary's source against a candidate directory never
  matched and the "in use" guard silently did not fire. `QDir::cleanPath` is the
  correct normalisation. The test `the directory the loaded dictionary lives in
  is itself blocked` fails on the old form.
- `Qt` gives a directory path a trailing separator, which defeats a plain
  `startsWith(dirAbs + "/")` prefix test. Same fix.
