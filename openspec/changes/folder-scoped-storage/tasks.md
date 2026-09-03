## 1. Java shell: SAF picker + result handling

- [x] 1.1 Add `pickDictionaryFolder()` static on `ExperimentActivity`: launch `ACTION_OPEN_DOCUMENT_TREE` with `FLAG_GRANT_READ|WRITE|PERSISTABLE_URI_PERMISSION` and set a pending-result marker.
- [x] 1.2 Override `onActivityResult`: on OK, take the persisted URI permission, `resolveTreePath` (as a display label only — staging is always used, since scoped storage blocks direct-path reads), and write the new source (uri + staged path + display) to `shared_prefs/source.xml` for the C++ poller. **Verified on-device**: `onActivityResult` fires and the picker→source flow works after `pm clear com.google.android.documentsui` (the device's DocumentsUI was in a broken state).
- [x] 1.3 Implement `resolveTreePath(uri)`: `DocumentsContract.getTreeDocumentId` → `primary:<rel>` → `/storage/emulated/0/<rel>`, `<vol>:<rel>` → `/storage/<vol>/<rel>`, else empty (unresolvable).
- [x] 1.4 Implement `stageTree(uri, destDir)`: enumerate the `DocumentFile` tree (top level) for `.mdx`/`.mdd`/`.dsl`/`.dsl.dz`/`.ifo` and copy them into `files/staged/<sourceId>/`.

## 2. C++ controller: sources model + scan

- [x] 2.1 Persist a `sources` array in `settings.json`: `[{ "uri", "path"?, "staged" }]` (load on init, save on change); keep the sandbox `files/staged` as an always-on source.
- [x] 2.2 Add the poller branch that consumes the Java source file → append the new source, persist, and rescan.
- [x] 2.3 Rework `runScan`: loop the sources, call `gd_scan_dicts` per resolvable physical dir (resolved path or staged subdir), accumulate `dictCount`; skip unavailable/revoked sources without failing the others; drop the AFA branch.
- [x] 2.4 Remove AFA helpers (`isAllFilesAccessGranted`/`openAllFilesAccessSettings`/`externalStoragePath`) and `externalStoragePath` usage; add `Q_INVOKABLE addDictionaryFolder()` (calls `pickDictionaryFolder`) and `Q_INVOKABLE removeSource(int index)`.
- [x] 2.5 Expose the sources list to QML (model + change signal) and a `sources` getter.

## 3. QML: Add-dictionaries flow

- [x] 3.1 Remove the `storageGranted` timer and the storage-grant branch: "Add dictionaries" always opens the SAF picker (via `engine.addDictionaryFolder()`).
- [x] 3.2 Add a "Sources" list to the Dicts pane: each source shows its display name (and path / "(staged)") with a remove action calling `engine.removeSource(index)`.
- [x] 3.3 Update onboarding + hints to describe the folder-picker flow and drop any All-Files-Access wording.

## 4. Manifest + cleanup

- [x] 4.1 Remove `android.permission.MANAGE_EXTERNAL_STORAGE` from `AndroidManifest.xml`.
- [x] 4.2 Confirm no remaining references to `isAllFilesAccessGranted`/`openAllFilesAccessSettings`/`externalStoragePath`/`MANAGE_EXTERNAL_STORAGE` in the repo.

## 5. On-device verification

- [x] 5.1 Add dictionaries: picker opens; picking a folder with dicts scans (staged) and lists them. **Verified end-to-end on-device**: DocumentsUI pick → Allow → source persisted `staged:true` → files stage-copied → `scan -> 2` → dictionaries listed and **searchable** (`suggest ready count=16`).
- [x] 5.2 Restart persistence: after a restart the source is still listed and its dictionaries auto-load without re-picking. **Verified** via force-stop → relaunch.
- [x] 5.3 Multiple sources: adding a second folder combines dictionaries from both. **Verified** (two staged sources → 2 dicts listed, both sources shown).
- [x] 5.4 Remove a source: its dictionaries vanish from the list, lookups, and full-text search without affecting other sources. **Verified** (dict unloaded via `gd_remove_dict`).
- [ ] 5.5 Fallback: an unresolvable provider is stage-copied and scanned; no system-wide permission is ever requested. **Partial** — staging+scan verified through the poller path; `MANAGE_EXTERNAL_STORAGE` fully removed.
- [x] 5.6 Rescan re-pulls the ORIGINAL folders, not the staging (`rescan` → Java `refreshSources` → incremental `stageTree` → `refresh.xml` → `runScan`). **Verified**: unchanged source → `copied=0`, marker consumed, scan re-runs.
- [x] 5.7 Remove a source deletes its staged private copy. **Verified**: `removing staged copy <dir>` + dir gone, dicts unloaded (`setDictionaries count=0`). The original user folder is never touched.

## 6. Follow-up: recursive dictionary scan (carve)

Planned as a distinct item, deliberately NOT part of this change's acceptance.
Nested subfolders (e.g. `GoldenDict/English/`) are currently skipped because the
carve's `collectFiles` (`carve/gd_boundary.cc`) scans a directory top-level only
(`QDir::entryInfoList(..., QDir::Files)`, no `Subdirectories`).

- [ ] 6.1 Make the carve `collectFiles` recursive (`QDir::entryInfoList` → `QDirIterator` with `QDirIterator::Subdirectories`), so a scanned folder includes dictionaries in nested folders.
- [ ] 6.2 Update the CI engine-smoke expectations (fixture uses flat dirs, so `gd_scan_dicts -> N` still holds; add a nested fixture to assert recursion) and the carve/goldendict.h doc comment.
- [ ] 6.3 Re-verify on-device: picking a folder whose dicts live in subfolders loads them.
    Note: this is a carve/boundary change → also touch `patches/` + smoke per the repo golden rules.
