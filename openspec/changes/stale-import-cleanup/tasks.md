## 1. Shared cleanup routine

- [ ] 1.1 Add a routine on `EngineController` that takes a staged directory and
  removes it, its index entries, and its `staging-tmp` sibling — following the
  existing `deleteDictionaryFiles` shape (`EngineController.cpp:984-1033`)
- [ ] 1.2 Make it refuse any path that does not resolve inside the staged root
  (reuse `stagedAncestor`), and log the refusal; deleting outside the staged root
  must be impossible through this path
- [ ] 1.3 Make it skip any directory that a **loaded** dictionary still uses
  (same "shared by siblings" check as `deleteDictionaryFiles`), so a shared
  import folder keeps its working members
- [ ] 1.4 Have `deleteDictionaryFiles` delegate its directory-removal step to the
  new routine, so the guard exists once instead of twice

## 2. Remove a reported failure

- [ ] 2.1 Add an invokable (e.g. `removeScanFailure(file)`) that removes the
  staged directory containing the reported file and drops that entry from
  `m_scanFailures`, emitting `scanFailuresChanged`
- [ ] 2.2 Handle the case where the file is already gone (the directory was
  removed by other means): drop the entry rather than erroring
- [ ] 2.3 Confirm no BOM/bridge change is needed — `gd_scan_failures` already
  returns the full path, so this is app-side only

## 3. Re-import supersedes a failed import

- [ ] 3.1 After a scan completes, collect the staged directories that produced
  **zero** loaded dictionaries and were reported as failures, and run the
  cleanup routine on each (not at staging time — see `design.md`, "after a
  successful scan")
- [ ] 3.2 Confirm this makes the existing banner advice true: re-importing the
  same folder clears the failure
- [ ] 3.3 Confirm a directory that yielded a loaded dictionary is never swept,
  including when it shares an import folder with a failing file
- [ ] 3.4 Confirm the sweep does not run when the user takes no action (scan
  alone must not delete anything)

## 4. Banner

- [ ] 4.1 Add a remove action to the failures banner in `app/main.qml`
  (`engine.scanFailures` block, ~line 1689) calling 2.1 for that row
- [ ] 4.2 Correct the copy: it currently says "Tap Add dictionaries and pick the
  same folder again to re-copy it", which does not clear the error. It should
  state what the user can do (remove the failed import, or re-import the folder)
  and be true once 3.x lands
- [ ] 4.3 Give the action a stable invariant English `Accessible.name` and add it
  to the `AGENTS.md` accessible-element table
- [ ] 4.4 Localization: extract and translate the new/changed strings in RU and JA
  (`scripts/update-translations.ps1`, then `app/i18n/*.ts`, then recommit the
  `.qm`), per the documented workflow

## 5. Automated coverage

- [ ] 5.1 Add host coverage for the path-containment guard: a path outside the
  staged root is refused, a path inside resolves to its directory
- [ ] 5.2 Add host coverage for the "shared by siblings" skip: a directory still
  used by a loaded dictionary is not removed
- [ ] 5.3 Build and run the host test targets; confirm the new assertions fail
  before the guard exists and pass after

## 6. Documentation

- [ ] 6.1 `docs/TESTING.md`: add recipes — remove a failed import and confirm the
  files are gone and the banner clears; re-import a previously-failed folder and
  confirm the failure clears without manual storage surgery
- [ ] 6.2 Remove or narrow any known-gap note that described this as unfixable
- [ ] 6.3 Update the `dictionary-management` spec via the archived delta, then
  archive the change

## 7. On-device verification

- [ ] 7.1 Import a folder that half-stages (or a corrupt dictionary) so a failure
  is reported, then use the banner action and confirm the files are deleted and
  the banner clears, with no other dictionary affected
- [ ] 7.2 Re-import the corrected folder and confirm the failure clears without
  touching app storage by hand
- [ ] 7.3 On a device that already carries an unresolvable failed import from
  before this change, confirm the new action clears it
- [ ] 7.4 Confirm RU/JA show the new/changed banner strings
