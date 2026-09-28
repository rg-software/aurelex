## 1. Catalog contract and fixture

- [x] 1.1 Write the manifest schema as a short doc comment/appendix: `schemaVersion`, `updated`, and `entries[]` with `id`, `name`, `langFrom`, `langTo`, `attribution`, `license`, and `files[]` (`role`, `required`, `name`, `url`, `sizeBytes`, optional `sha256`)
- [x] 1.2 Add a checked-in fixture catalog (`app/test/fixtures/catalog.json`) with at least three entries: one DSL pair with optional audio, one mdict pair (`.mdx` + `.mdd`) to exercise multi-file installed-detection, and one entry with a deliberately missing `sha256`
- [x] 1.3 Add a fixture with a malformed entry (missing `url`, non-numeric `sizeBytes`, unknown `role`) used to pin the parser's error handling
- [x] 1.4 Decide and record the hosting location (raw GitHub vs Pages) in the manifest doc, including the caching/probe implications — does not change the schema

## 2. Catalog fetch and parse (C++)

- [x] 2.1 Add a `CatalogEntry` struct (id, name, lang pair, attribution, license, derived total size, per-file list) and a parser for the manifest that is total: it rejects the document rather than throwing on a bad entry
- [x] 2.2 Derive each entry's total download size from its file list; do not store it in the manifest
- [x] 2.3 Implement installed-detection: an entry is installed when every file with `role: "dictionary"` has its basename present in the basenames of `dictionaries[].source`
- [x] 2.4 Fetch the manifest with `QNetworkAccessManager` over HTTPS with a timeout; on any failure report unreachable and leave the last-good manifest in place
- [x] 2.5 Cache the last-good manifest and its fetch timestamp; do not fetch during app startup
- [x] 2.6 Add a parser unit test covering fixtures 1.2 and 1.3 (installed-detection for the mdict pair, the missing-`sha256` entry, and each malformed case)

## 3. Settings

- [x] 3.1 Add `remoteCatalogUrl` to `loadSettings()`/`saveSettings()` in `EngineController`, defaulted from a compiled-in HTTPS constant when the key is absent
- [x] 3.2 Confirm an app built before this change loads with the default and re-writes the key without a migration (absent key path)

## 4. Download service (Java)

- [x] 4.1 Add `DictionaryDownloadService` as a `dataSync` foreground service in `AndroidManifest.xml`, mirroring `StagingService`
- [x] 4.2 Implement the transfer loop over `HttpURLConnection`: bounded buffer, per-file progress, running speed, and a per-iteration cancel-flag check
- [x] 4.3 Download into `files/staging-tmp/<contentHash>/` where `<contentHash>` derives from the entry id plus its required file names — not from the URL
- [x] 4.4 Atomic-rename the completed entry into `files/staged/<contentHash>/`, exactly as `StagingService.stageOne` does; never leave a partial where the engine can see it
- [x] 4.5 Verify `sha256` per file when the manifest supplies one; on mismatch delete the file, mark the entry failed, and name the entry in the reported failure. Skip verification when absent
- [x] 4.6 Free-space preflight before the first byte: refuse below `bundleBytes + 512 MiB` with the shortfall named; warn below `bundleBytes + 2 GiB`. Put both constants in one place
- [x] 4.7 Batch semantics: process selected entries in turn, one foreground notification for the whole batch, and a single cancel that aborts all of them and reports *cancelled* (not *failed*)
- [x] 4.8 One entry failing does not abort the rest of the batch; the failure names the entry and the others still complete
- [x] 4.9 Resume via `Range` + `If-Range` (ETag/Last-Modified); on `200`-for-`Range`, a changed validator, or a short read, restart that file from zero
- [x] 4.10 On service start, reconcile orphaned `staging-tmp/<contentHash>` dirs: resume if the entry is still in the catalog, purge otherwise
- [x] 4.11 Write progress to `shared_prefs/download.xml` (active, entry name, files done/total, bytes done/total, speed, outcome) and clear it on every terminal outcome
- [x] 4.12 Notification carries a determinate progress bar (unlike the current indeterminate staging notification) and stops on terminal outcome

## 5. Hand-off to the engine

- [x] 5.1 Read `download.xml` in the existing 500 ms poller (`EngineController.cpp` ~2104) and expose it as download properties; clear the marker on terminal outcome
- [x] 5.2 On batch success, raise the existing staging marker so the current chain (`runScan` → `autoIndexMissing` → `refreshDictionaries`) picks the new files up unchanged
- [x] 5.3 Verify a download never sets or clears `processingActive`, and that cancelling a download while a scan/index is live leaves the banner correct
- [x] 5.4 Verify `purgeStagingTmp()` cannot race an active download (download scratch is content-hash keyed, SAF scratch is URI-hash keyed)
- [x] 5.5 Verify re-downloading an installed entry produces one list row, not two
- [x] 5.6 Verify a killed download leaves no partial that surfaces in `scanFailures`

## 6. Catalog UI (QML)

- [x] 6.1 Add "Add from remote" next to the existing Add action in the Dictionaries pane, opening the catalog in place over the pane (no new tab, no dock slot)
- [x] 6.2 List entries with name, language pair, total size, and an installed badge; multi-select for batch download
- [x] 6.3 Disable "Add from remote" with a stated reason when the catalog is unreachable; leave the folder import action untouched
- [x] 6.4 Show a last-known catalog read-only when offline, with per-entry download attempts reporting the catalog as unreachable
- [x] 6.5 Free-space refusal and warning dialogs, naming the entry and the shortfall
- [x] 6.6 Per-entry "Add audio" action for installed entries that have optional resources
- [x] 6.7 Add `Accessible.name` + `Accessible.role` to every new interactive element and record the new element IDs in `AGENTS.md`'s accessible-ID table

## 7. Download progress and cancel UI

- [x] 7.1 Download progress surface: fraction, current entry, transferred/total, speed — kept visually distinct from the existing processing banner so the two never read as one chain
- [x] 7.2 Cancel action that aborts the whole batch and shows a *cancelled* outcome, distinct from failure
- [x] 7.3 Failure reporting naming the affected entry, with successful entries from the same batch still listed
- [x] 7.4 Verify the download UI does not disable the Dicts Remove button or the FTS controls

## 8. Audio add-later reload

- [x] 8.1 On completing an optional-resource download for an already-loaded dictionary, call `gd_remove_dict` for that dictionary and re-run the scan so the resources take effect
- [x] 8.2 Verify the dictionary keeps its existing FTS index (no `autoIndexMissing` re-run for it) and that `ftsIndexState` still reports it built
- [x] 8.3 Verify the dictionary keeps its list position and group membership across the reload
- [x] 8.4 Verify no app restart is needed for the audio to become playable

## 9. Docs

- [x] 9.1 Amend the `README.md` privacy claim — the app now makes outbound requests and does use the network beyond the WebView
- [x] 9.2 Amend the `docs/DESIGN-v2.md` "Search in online dictionaries" non-goal to reflect a curated install catalog (still no online *lookup*)
- [x] 9.3 Add a `docs/REMOTE-CATALOG.md` covering the manifest format, how to host it, and how to add an entry
- [x] 9.4 Note the new milestone in `docs/ROADMAP.md` and cross-link the `fts-indexing-performance` known limitation (engine mutex held for the whole build)

## 10. Localization

- [x] 10.1 Run `scripts/update-translations.ps1` and translate every new catalog entry in `app/i18n/*.ts`
- [x] 10.2 Mirror new `app/android/res/values/strings.xml` strings in `values-ru/` and `values-ja/`
- [x] 10.3 Recompile and recommit `app/i18n/*.qm`

## 11. Verification

- [x] 11.1 Confirm `carve/`, `patches/`, and the CI smoke test are untouched — this change is app-side only
- [x] 11.2 Confirm `network_security_config.xml` is unchanged and the catalog URL is HTTPS
- [x] 11.3 Confirm the app still requests no storage permission on any path, including the catalog path
- [x] 11.4 Run `openspec validate remote-dictionary-catalog --strict`

## Notes on deviations

- **1.2** — the fixture lives at `app/tests/fixtures/catalog.json`, matching the
  existing host-test convention (`app/tests/` already holds `ArticleServerTest`,
  `IndexCleanupTest`, `IndexMigrationTest`), not the `app/test/` path in the task
  text. The test target is `catalog_test` in `app/tests/CMakeLists.txt`.
- **5.2** — a completed batch calls the existing chain directly
  (`runScan()` → `autoIndexMissing()` → `refreshDictionaries()`) instead of
  writing the Android `shared_prefs/staging.xml` marker that `StagingService`
  owns. The effect on the engine is identical (the chain is reused unchanged);
  writing another Android shared-prefs file from C++ only to read it back in the
  same process would add a spurious "Staging" banner and a second writer for a
  file with one owner.

## Device verification (2026-09-28, Motorola ThinkPhone / Android)

Built and installed the Debug APK (`app/build.ps1 -Configuration Debug -Install`)
and exercised the feature against a throwaway HTTPS catalog hosted on a public
gist (since the compiled-in Pages URL is not published yet). The device had no
network, so it was routed through a host-side CONNECT proxy via `adb reverse`.

Verified on device:

- Catalog fetch over HTTPS, cache, 7-entry list, installed badges, unsupported
  entry listed/disabled, offline read-only notice.
- Batch download published to `files/staged/<contentHash>/` and handed to the
  scan → auto-index chain; the dictionary appears in the Dicts list.
- Partial-failure batch: outcome names the failed entry and lists the successful
  one; the successful entry is indexed (4.8, 7.3).
- Failed entry leaves a `.part` in `staging-tmp` (kept for resume) and never
  surfaces in `scanFailures` (5.6).
- Re-install/installed entries show as installed and cannot be re-downloaded;
  content hash is content-derived, so no duplicate row (5.5).
- Audio add-later: `gd_remove_dict` + rescan ran, the bundle landed beside the
  `.dsl`, and the dictionary's `_FTS_x` index kept its original mtime while the
  main index was rewritten — the FTS index is preserved (8.1-8.4). Playback of
  the resource itself is the only manual step (the fixture has a placeholder).

Bugs found by device testing and fixed in this change:

1. **No TLS at all.** The APK shipped the Qt OpenSSL plugin but not
   `libcrypto`/`libssl`, so every Qt HTTPS call failed with *TLS initialization
   failed*. Fixed by vendoring OpenSSL 3 libs in `app/openssl/<abi>/` and
   adding them to `QT_ANDROID_EXTRA_LIBS` (see design D12 correction).
2. **Download outcome never parsed.** SharedPreferences stores `<string>`
   values as element TEXT, but `syncDownloadState()` read a `value` attribute,
   so `entryName`/`succeeded`/`failed`/`scratchHashes` were always empty. The
   terminal outcome was never produced, the marker was never consumed, and a
   downloaded dictionary was never scanned in. Fixed with `readElementText()`.
3. **JNI abort on download start.** `QJniObject::callStaticMethod` was passed a
   `const char*` for a `Ljava/lang/String;` parameter, aborting the process with
   *jobject is an invalid JNI transition frame reference*. Fixed with
   `QJniObject::fromString(...).object<jstring>()`.
4. **`refreshCatalog()` was a no-op.** `fetchCatalog()` treated an invalid
   timestamp as "fresh" and returned the cache without issuing a request. Fixed
   the gate to only short-circuit on a valid, recent timestamp.
5. **Reachability not persisted.** After a restart the cached catalog rendered
   read-only and downloads were refused until a manual re-probe. Fixed by
   persisting `remoteCatalogReachable` and restoring it with the cached manifest.
6. **"Add audio" untappable.** The button lives inside a delegate whose
   `enabled:false` (installed entries) disabled its children. Fixed by not
   disabling the row and guarding the selection tap instead.
7. **SIGSEGV ~15 s after every catalog fetch.** The fetch-timeout
   `QTimer::singleShot` captured the `QNetworkReply` as a raw pointer, but the
   finished handler `deleteLater()`s it, so the timeout dereferenced freed
   memory on the UI thread (`fetchCatalog()::…` ← `QTimerInfoList::activateTimers`).
   Fixed by capturing a `QPointer<QNetworkReply>`. Surfaced only because the
   test session outlived the 15 s timer; earlier rounds rebuilt/restarted first.

## Follow-up UI rework (implemented 2026-09-28)

Interaction agreed with the maintainer and shipped:

- **Dicts toolbar:** the catalog entry point is icon-only (`cloud_download`,
  highlighted accent) next to `Add`; `Add` and `Remove` lost their text
  captions; `Remove` is the existing `delete` (trash) glyph.
- **Catalog surface:** a full-page pane (like the group-membership editor), not
  a modal sheet — top-left `arrow_back`, title + status line, and a master
  download button that becomes cancel (X) while a batch runs. No Close/Refresh
  buttons; opening the pane re-probes the catalog itself.
- **Per-entry audio (opt-out):** the row has a music toggle. Selecting a name
  selects the entry and its audio; the note opts the audio back out. Installed
  rows are not selectable except for the note, which adds a missing bundle.
  `music_note`/`music_off` and the `audio` request flag + `resourcesPresent`
  model field back this.
- **Progress:** no banners/buttons — just a `ProgressBar` and a one-line note;
  a completed entry greys out as installed, and the selection clears when the
  rescan marks it installed.
- **Icon font:** `cloud_download`, `sync`, `music_note`, `music_off` and
  `refresh` are all present in the bundled **classic** `MaterialIcons-Regular`
  font (verified), so no subset regeneration was needed — the carve script is
  only for Symbols-only glyphs like `match_word`.
- **Catalog URL:** `kDefaultRemoteCatalogUrl` is pointed at the maintainer's
  Seafile share for real-condition testing; replace with the final hosted URL
  before release.

Two bugs surfaced by this rework and fixed: `refreshCatalogEntries()` never
emitted `catalogChanged()`, so the scan path left stale installed badges /
selection until the pane was reopened; and `downloadPreflight` returned early
with no `freeBytes` when the computed need was zero, rendering an empty-placeholder
"not enough space" dialog (now a `nothing` flag, no dialog).
