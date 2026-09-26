## 1. Catalog contract and fixture

- [ ] 1.1 Write the manifest schema as a short doc comment/appendix: `schemaVersion`, `updated`, and `entries[]` with `id`, `name`, `langFrom`, `langTo`, `attribution`, `license`, and `files[]` (`role`, `required`, `name`, `url`, `sizeBytes`, optional `sha256`)
- [ ] 1.2 Add a checked-in fixture catalog (`app/test/fixtures/catalog.json`) with at least three entries: one DSL pair with optional audio, one mdict pair (`.mdx` + `.mdd`) to exercise multi-file installed-detection, and one entry with a deliberately missing `sha256`
- [ ] 1.3 Add a fixture with a malformed entry (missing `url`, non-numeric `sizeBytes`, unknown `role`) used to pin the parser's error handling
- [ ] 1.4 Decide and record the hosting location (raw GitHub vs Pages) in the manifest doc, including the caching/probe implications — does not change the schema

## 2. Catalog fetch and parse (C++)

- [ ] 2.1 Add a `CatalogEntry` struct (id, name, lang pair, attribution, license, derived total size, per-file list) and a parser for the manifest that is total: it rejects the document rather than throwing on a bad entry
- [ ] 2.2 Derive each entry's total download size from its file list; do not store it in the manifest
- [ ] 2.3 Implement installed-detection: an entry is installed when every file with `role: "dictionary"` has its basename present in the basenames of `dictionaries[].source`
- [ ] 2.4 Fetch the manifest with `QNetworkAccessManager` over HTTPS with a timeout; on any failure report unreachable and leave the last-good manifest in place
- [ ] 2.5 Cache the last-good manifest and its fetch timestamp; do not fetch during app startup
- [ ] 2.6 Add a parser unit test covering fixtures 1.2 and 1.3 (installed-detection for the mdict pair, the missing-`sha256` entry, and each malformed case)

## 3. Settings

- [ ] 3.1 Add `remoteCatalogUrl` to `loadSettings()`/`saveSettings()` in `EngineController`, defaulted from a compiled-in HTTPS constant when the key is absent
- [ ] 3.2 Confirm an app built before this change loads with the default and re-writes the key without a migration (absent key path)

## 4. Download service (Java)

- [ ] 4.1 Add `DictionaryDownloadService` as a `dataSync` foreground service in `AndroidManifest.xml`, mirroring `StagingService`
- [ ] 4.2 Implement the transfer loop over `HttpURLConnection`: bounded buffer, per-file progress, running speed, and a per-iteration cancel-flag check
- [ ] 4.3 Download into `files/staging-tmp/<contentHash>/` where `<contentHash>` derives from the entry id plus its required file names — not from the URL
- [ ] 4.4 Atomic-rename the completed entry into `files/staged/<contentHash>/`, exactly as `StagingService.stageOne` does; never leave a partial where the engine can see it
- [ ] 4.5 Verify `sha256` per file when the manifest supplies one; on mismatch delete the file, mark the entry failed, and name the entry in the reported failure. Skip verification when absent
- [ ] 4.6 Free-space preflight before the first byte: refuse below `bundleBytes + 512 MiB` with the shortfall named; warn below `bundleBytes + 2 GiB`. Put both constants in one place
- [ ] 4.7 Batch semantics: process selected entries in turn, one foreground notification for the whole batch, and a single cancel that aborts all of them and reports *cancelled* (not *failed*)
- [ ] 4.8 One entry failing does not abort the rest of the batch; the failure names the entry and the others still complete
- [ ] 4.9 Resume via `Range` + `If-Range` (ETag/Last-Modified); on `200`-for-`Range`, a changed validator, or a short read, restart that file from zero
- [ ] 4.10 On service start, reconcile orphaned `staging-tmp/<contentHash>` dirs: resume if the entry is still in the catalog, purge otherwise
- [ ] 4.11 Write progress to `shared_prefs/download.xml` (active, entry name, files done/total, bytes done/total, speed, outcome) and clear it on every terminal outcome
- [ ] 4.12 Notification carries a determinate progress bar (unlike the current indeterminate staging notification) and stops on terminal outcome

## 5. Hand-off to the engine

- [ ] 5.1 Read `download.xml` in the existing 500 ms poller (`EngineController.cpp` ~2104) and expose it as download properties; clear the marker on terminal outcome
- [ ] 5.2 On batch success, raise the existing staging marker so the current chain (`runScan` → `autoIndexMissing` → `refreshDictionaries`) picks the new files up unchanged
- [ ] 5.3 Verify a download never sets or clears `processingActive`, and that cancelling a download while a scan/index is live leaves the banner correct
- [ ] 5.4 Verify `purgeStagingTmp()` cannot race an active download (download scratch is content-hash keyed, SAF scratch is URI-hash keyed)
- [ ] 5.5 Verify re-downloading an installed entry produces one list row, not two
- [ ] 5.6 Verify a killed download leaves no partial that surfaces in `scanFailures`

## 6. Catalog UI (QML)

- [ ] 6.1 Add "Add from remote" next to the existing Add action in the Dictionaries pane, opening the catalog in place over the pane (no new tab, no dock slot)
- [ ] 6.2 List entries with name, language pair, total size, and an installed badge; multi-select for batch download
- [ ] 6.3 Disable "Add from remote" with a stated reason when the catalog is unreachable; leave the folder import action untouched
- [ ] 6.4 Show a last-known catalog read-only when offline, with per-entry download attempts reporting the catalog as unreachable
- [ ] 6.5 Free-space refusal and warning dialogs, naming the entry and the shortfall
- [ ] 6.6 Per-entry "Add audio" action for installed entries that have optional resources
- [ ] 6.7 Add `Accessible.name` + `Accessible.role` to every new interactive element and record the new element IDs in `AGENTS.md`'s accessible-ID table

## 7. Download progress and cancel UI

- [ ] 7.1 Download progress surface: fraction, current entry, transferred/total, speed — kept visually distinct from the existing processing banner so the two never read as one chain
- [ ] 7.2 Cancel action that aborts the whole batch and shows a *cancelled* outcome, distinct from failure
- [ ] 7.3 Failure reporting naming the affected entry, with successful entries from the same batch still listed
- [ ] 7.4 Verify the download UI does not disable the Dicts Remove button or the FTS controls

## 8. Audio add-later reload

- [ ] 8.1 On completing an optional-resource download for an already-loaded dictionary, call `gd_remove_dict` for that dictionary and re-run the scan so the resources take effect
- [ ] 8.2 Verify the dictionary keeps its existing FTS index (no `autoIndexMissing` re-run for it) and that `ftsIndexState` still reports it built
- [ ] 8.3 Verify the dictionary keeps its list position and group membership across the reload
- [ ] 8.4 Verify no app restart is needed for the audio to become playable

## 9. Docs

- [ ] 9.1 Amend the `README.md` privacy claim — the app now makes outbound requests and does use the network beyond the WebView
- [ ] 9.2 Amend the `docs/DESIGN-v2.md` "Search in online dictionaries" non-goal to reflect a curated install catalog (still no online *lookup*)
- [ ] 9.3 Add a `docs/REMOTE-CATALOG.md` covering the manifest format, how to host it, and how to add an entry
- [ ] 9.4 Note the new milestone in `docs/ROADMAP.md` and cross-link the `fts-indexing-performance` known limitation (engine mutex held for the whole build)

## 10. Localization

- [ ] 10.1 Run `scripts/update-translations.ps1` and translate every new catalog entry in `app/i18n/*.ts`
- [ ] 10.2 Mirror new `app/android/res/values/strings.xml` strings in `values-ru/` and `values-ja/`
- [ ] 10.3 Recompile and recommit `app/i18n/*.qm`

## 11. Verification

- [ ] 11.1 Confirm `carve/`, `patches/`, and the CI smoke test are untouched — this change is app-side only
- [ ] 11.2 Confirm `network_security_config.xml` is unchanged and the catalog URL is HTTPS
- [ ] 11.3 Confirm the app still requests no storage permission on any path, including the catalog path
- [ ] 11.4 Run `openspec validate remote-dictionary-catalog --strict`
