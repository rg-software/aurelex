## 1. Boundary inventory (additive; the only carve change)

- [x] 1.1 Add `gd_dict_identity( int index, char * out, int out_size )` to
  `carve/goldendict.h`, returning the display name, the primary file path and the
  complete source-file set for dictionary `index`, serialized as the existing
  buffer/NUL-terminated `gd_dict_info` convention: `D<TAB>name<TAB>primaryPath`
  then `F<TAB>basename<TAB>size<TAB>mtimeMs` per file. Document each field, the
  recommended buffer size, and the resource-tree exclusion in the header comment
  (no engine change, no existing signature altered).
- [x] 1.2 Implement it in `carve/gd_boundary.cc` as raw file records, NOT a
  digest: the caller must compare them with the 5000 ms mtime tolerance the
  importer already applies, and a digest cannot express a tolerance
  (design.md D2). Strip the directory to `QFileInfo::fileName()` so the same
  dictionary in two staged roots compares equal, include every file rather than
  only the primary, and report `-1` for the size and mtime of a missing file to
  match what `stampSourceFiles()` records for an absent one. Comment why
  `getDictionaryFilenames()` — not the sibling resource tree — is the unit.
- [x] 1.3 Return `-2` for an index that does not exist, distinct from the `-1`
  the neighbouring `gd_dict_*` calls use for invalid args and buffer too small, so
  a caller can tell "this dictionary is gone" (a concurrent removal) from "give me
  a bigger buffer" and drop the entry rather than retrying forever.
- [x] 1.4 Verify the carve still compiles with the smoke tool before going further
  — this is the gate that catches a bad include or a vector-lifetime bug early.

## 2. Identity resolution on the app side

- [x] 2.1 Implement name normalization (case-fold, trim, collapse internal
  whitespace) in `app/DictIdentity.hpp` as a single function with the rationale in
  a comment (design.md D7). Format is never part of the key.
- [x] 2.2 Add a helper that groups the loaded inventory by normalized name
  (`DictIdentity::groupByName`, plus `EngineController::duplicateGroups`, which
  drops groups of one), returning per identity the members with their file records
  and primary file path. The staged ancestor is deliberately NOT precomputed: it is
  derived on demand in `deleteIdentityFiles`, because the sharing guard that
  consumes it must be judged against the engine's dictionary set *after* the
  unload, and a value captured before it is stale exactly when it matters.
- [x] 2.3 Add a helper comparing two file sets for equality
  (`DictIdentity::sameContent`), so the tolerance lives in one place and is not
  re-implemented per call site.
- [x] 2.4 Read the whole inventory off the UI thread (the existing
  `QtConcurrent` + `QFutureWatcher` pattern from `runScan` / `autoIndexMissing`);
  `gd_dict_identity` takes `g_engineMutex`, so calling it inline would freeze the
  app behind a running FTS build.

## 3. Scan-time invariant (this is what fixes existing installs)

- [x] 3.1 Run the identity grouping after **every** scan completes — in the same
  watcher callback that calls `collectScanFailures` — not only on import, so
  duplicates already on disk are resolved on the first scan after upgrade and do
  not return on restart (design.md D5). The rest of the scan chain runs from its
  continuation, so the collapse is finished before the stale-dir sweep and the
  refresh read the dictionary list.
- [x] 3.2 For each identity with more than one member and **equal** file sets,
  collapse it silently: keep the lowest engine index and delete the other members'
  staged files, so nothing outside the staged root and no directory still holding a
  kept dictionary is removed. The deletion is per FILE SET plus the directory
  reclaim, via `deleteIdentityFiles` — the whole-directory-only sweep cannot free a
  file from a folder shared with dictionaries that loaded.
- [ ] 3.3 Unload the collapsed duplicates (`gd_remove_dict`) and refresh the list
  and groups. Confirm the survivor keeps its position and its group membership.
  (Implementation done in `unloadAndDelete`; the "confirm" half is on-device
  verification — task 5.8.)
- [x] 3.4 For each identity whose members **differ**, change nothing: leave every
  member loaded and stored, and record the name as a conflict. A group is
  all-or-nothing — if any pair differs, no member of it is collapsed, because the
  comparison cannot say which build the user wants.
- [ ] 3.5 Report conflicts through the `report-import-results` surface, with
  wording that does **not** reuse the load-failure text — in particular it must
  not tell the user to remove the file and import the folder again
  (`main.qml:1786`), which is untrue for a clash.
  (Conflicts are already collected into `m_nameClashes` as `{name, count}` and
  logged. Rendering them needs `report-import-results`, which is not built yet.)
- [ ] 3.6 Confirm the report clears when the user resolves the conflict by
  removing one of the pair, and does not reappear on later scans.

## 4. Import path: skip and reject

- [ ] 4.1 After a staged import's scan, identify the newly loaded dictionaries
  (those whose staged ancestor was not present before the pick) and group them
  against the incumbents.
- [ ] 4.2 Implement the shared mechanic (design.md D3): unload the candidate with
  `gd_remove_dict`, delete its file set, reclaim the staged directory only when no
  loaded dictionary remains in it. Confirm the reclaim covers the whole file set,
  including any `<dict>.dsl.files/` resource tree, and refuses a directory that
  still holds a kept sibling.
- [ ] 4.3 Equal signature → keep the incumbent untouched and report **nothing**:
  no message, no row, no prompt (the "silently skipped" requirement).
- [ ] 4.4 Differing signature → keep the incumbent untouched and report the clash
  by name with the reason, asking the user nothing.
- [ ] 4.5 Verify a pick mixing a clashing dictionary with ten new ones imports and
  indexes all ten and is not presented as a failed import.
- [ ] 4.6 Verify remove-then-reimport resolves a clash: after removing the
  installed dictionary, the same pick imports the new build normally.

## 5. Verification

- [ ] 5.1 Add a smoke fixture pair to `carve/smoke/main.cpp`: two copies of one
  dictionary at **different paths** (same name, same file set), asserting the
  scan-time invariant collapses them and reports nothing — the CI gap that let the
  original bug ship.
- [ ] 5.2 Add the differing-content fixture pair, asserting both remain loaded and
  the conflict is reported — the "report, do not resolve" behaviour.
- [ ] 5.3 Assert in the smoke tool that the signature is location-independent: the
  same file staged under two directories yields one signature (design.md D2).
- [x] 5.4 Add a host-side test for name normalization (case, trailing and doubled
  whitespace) alongside the existing `app/tests` coverage.
  (`app/tests/DictIdentityTest.cpp` + a `dict_identity_test` target: 25 checks
  covering normalization, file-set comparison incl. the mtime tolerance, the
  record round-trip incl. a TAB inside a name, and grouping. All pass.)
- [ ] 5.5 On device: keep dictionaries in one folder, add a new dictionary to it,
  re-import — confirm the new one is added, the existing ones are unchanged and
  nothing is reported.
- [ ] 5.6 On device: pick a folder, then pick its parent — confirm one dictionary,
  no second copy on disk, intact group membership.
- [ ] 5.7 On device: import a different build of an installed dictionary from
  another folder — confirm no prompt, the old build unchanged, the new one
  reported, and the other dictionaries in the pick indexed normally.
- [ ] 5.8 With duplicates already present before the upgrade, confirm the first
  scan after upgrade collapses them without a re-import.
- [ ] 5.9 Run the CI smoke workflow and record the results in `docs/TESTING.md`.

## 6. Follow-up (record only if observed)

- [ ] 6.1 If the device pass shows a dictionary whose format hides its name from
  the engine, record it in `docs/TESTING.md` rather than adding a Java-side name
  parser — a second name implementation that can disagree with the engine's is the
  failure mode design.md D1 rejects.
