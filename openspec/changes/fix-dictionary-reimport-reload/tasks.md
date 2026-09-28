## 1. Root cause

- [x] 1.1 Confirm `gd_scan_dicts` runs the backend factory for every primary file before checking the id, so `Dsl::makeDictionaries` rewrites the index and the freshly built object is then discarded (`carve/gd_boundary.cc`)
- [x] 1.2 Confirm the dictionary id is an MD5 of the source paths, so a re-import into the same folder/file name keeps the id and the dedup cannot see the change
- [x] 1.3 Confirm on device: `gd_suggest word=swop mutex=0ms pump=9870ms finished=0` plus `Index searching failed: "kaikki-en", error: Error reading from the file`, and that a restart clears it

## 2. Fix - reload a changed dictionary

- [x] 2.1 Add `EngineState::SourceStamp` (size + mtime) and a per-id stamp map
- [x] 2.2 Add `stampSourceFiles` / `dictionarySourceChanged` helpers in the boundary
- [x] 2.3 In `gd_scan_dicts`, drop loaded entries whose source files no longer match, before the `loadedIds` dedup and before `before` is captured (so a reload counts as newly loaded)
- [x] 2.4 Record stamps for every dictionary the scan keeps
- [x] 2.5 Confirm an unchanged re-scan still loads nothing and does not touch the existing dictionaries' full-text state

## 3. Regression guard

- [x] 3.1 Add a re-import block to `carve/smoke/main.cpp`: append a new headword to a fixture, re-scan, and assert the scan reloads it (`REIMPORT_RELOAD`)
- [x] 3.2 Assert the appended headword resolves (`REIMPORT_CONTENT`) and prefix-searches (`REIMPORT_SUGGEST`)
- [x] 3.3 Fold the block into the tool's exit code
- [x] 3.4 Add the matching `grep` gates to `.github/workflows/engine-smoke.yml`
- [x] 3.5 Verify both ways: with the drop disabled all three assertions FAIL and the tool exits 1; with it enabled all three pass and it exits 0
- [x] 3.6 Run the full smoke and confirm every other assertion still passes

## 4. On-device verification

- [ ] 4.1 Search a word in a group, then re-import an updated build of that dictionary (same folder/name), let import + indexing finish, and confirm typing still shows a dropdown
- [ ] 4.2 Confirm the updated data is live without a restart (a headword only in the new build resolves)
- [ ] 4.3 Confirm the app does not die after the re-import (no `gd_suggest ... finished=0` in logcat, no foreground-service timeout)
