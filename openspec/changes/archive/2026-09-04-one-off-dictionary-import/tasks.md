# Tasks

- [x] **EngineController: drop `m_sources` + source management** (design D1)
  - Remove `m_sources`, `sources()`/`sourcesChanged`, `removeSource`,
    `rescan()`, `addDictionaryFolder`→source semantics, `ingestPendingSource`,
    `peekPendingSourceUri`, `removePendingSourceFile`,
    `peekPendingRefreshFlag`, `removePendingRefreshFile`,
    `loadSettings/saveSettings` `sources` persistence.
  - Keep `addDictionaryFolder()` (the picker launcher) — it no longer records
    a source; the picker just stage-copies a folder and triggers a scan.
- [x] **Java: import = stage-copy only** (design D1)
  - `AurelexActivity`: SAF picker still opens; drop `takePersistableUriPermission`
    persistence + `source.xml` write; after staging (via service), release the
    transient grant.
  - `StagingService`: stop writing `source.xml`; keep staging marker +
    `staging.xml` for UI; on completion signal the poller to `runScan()` (scan
    the staged root).
  - Remove `releaseSourcePermission` usage and `refreshSources` (no Rescan).
- [x] **Remove = permanent delete** (design D2)
  - In `EngineController::removeDictionary`, after `gd_remove_dict`:
    - resolve `gd_dict_info(index)` source path;
    - walk up to `files/staged/<id>`; delete the dir if no other loaded dict
      uses it;
    - delete `files/index<md5>[*]`, `index<id>_FTS_x`, `_temp`.
  - Refresh dicts / groups / FTS after removal.
- [x] **UI — drop Sources + Rescan** (design D3)
  - `main.qml` Dicts tab: remove Rescan button, Sources label + sources
    ListView; keep Add dictionaries + per-dict Remove.
  - Remove-dict confirm says the app's copy (files + index) will be deleted
    permanently.
  - Delete `engine.sources` references in QML.
- [x] **Docs**
  - Update `docs/*` (storage model, onboarding text maybe), `AGENTS.md`
    storage bullet.
- [ ] **Manual device verification**
  - Import folder → dicts appear; relaunch → still loaded (staged copy).
  - Remove a dict → gone from list/lookup/FTS, staged files + index deleted.
  - Existing app data: relaunch with old `settings.json` `sources` array → it
    is ignored, staged dicts still scan in. (Migration verified on-device.)