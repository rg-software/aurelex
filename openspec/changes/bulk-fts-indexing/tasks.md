## 1. Automatic bulk indexing

- [x] 1.1 Add `autoIndexMissing()` to `EngineController`: list dicts where `gd_fts_index_state==1`, build them sequentially in one `QtConcurrent::run` while `buildingFts` stays true, emit `ftsIndexChanged` per dict as each completes, then clear `buildingFts`.
- [x] 1.2 Call `autoIndexMissing()` from the `runScan` completion handler (after refreshDictionaries/refreshGroups), so it runs on initial load and every rescan; skip when `buildingFts` is already set.

## 2. UI: drop the per-dict Index button

- [x] 2.1 Remove the per-dictionary "Index" ToolButton from the Dicts pane row (indexing is automatic now).
- [x] 2.2 Keep the FTS pane's single indeterminate `buildingFts` ProgressBar ("Indexing..." label) covering the bulk build; verify it appears during a build.

## 3. Background service for long builds

- [ ] 3.1 Add an Android foreground `IndexingService` (Java) that runs the bulk `gd_fts_index` builds in a background thread with a foreground notification, driven by `EngineController` (in-process call).
- [ ] 3.2 Route the bulk build through the service so a long build continues when the app is backgrounded; signal completion back to `EngineController` via a shared-preferences marker (existing poller pattern) or a bound callback.
- [ ] 3.3 Add the service + notification-channel declarations to `AndroidManifest.xml`.

## 4. On-device verification

- [ ] 4.1 Add a dictionary (or rescan) with no FTS index → its index builds automatically, `buildingFts` shows the indicator, and a search returns results without a manual Index tap.
- [ ] 4.2 Add multiple dictionaries → all index in bulk, sequentially, and each becomes searchable as it completes.
- [ ] 4.3 Start a build on a large dictionary, background the app → the build continues on the service and completes.
- [ ] 4.4 Confirm there is no per-dictionary Index button and that the FTS pane works end-to-end.
