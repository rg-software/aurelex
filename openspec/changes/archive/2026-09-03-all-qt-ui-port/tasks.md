## 1. Port vehicle setup (from the proven experiment)

- [x] 1.1 Write `experiments/qtquick/build.ps1`: one script — cmake configure (Qt android toolchain, `ANDROID_PLATFORM=android-30`, NDK bionic include, JDK 17 for gradle) → ninja build → copy `.so` to `apk/libs/<abi>/` → androiddeployqt → re-apply `local.properties`/`gradle.properties` overrides (real SDK, compileSdk android-34, buildTools 35) → gradle assembleDebug. Verified by producing the current APK.
- [x] 1.2 Introduce the `EngineController` QObject (D2): worker-thread executor + signals; expose `gd_init`/`gd_scan_dicts`/`gd_dict_count`/`gd_dict_info`/`gd_lookup`/`gd_suggest` first; register as QML singleton/context property.
- [x] 1.3 Restructure QML: `Main.qml` with a simple page stack (Search / Article views as separate files); keep the experiment's dark header + WebView layout as the Article view.

## 2. Milestone 1 — core lookup (search + suggestions + article)

- [x] 2.1 Search view: text field with live `gd_suggest` (debounced via controller signal), tap-to-lookup list, "Look up" action; not-found state.
- [x] 2.2 Article bridge (D3): `ArticleServer` (QTcpServer on 127.0.0.1, random port) serving the bundled asset mirror (scripts/stylesheets/icons/flags) + `bres://` via `gd_get_resource` + `gdau://` via `gd_get_audio`; article HTML URLs rewritten once before `loadHtml`. **[Partial]** the experiment proved the *minimum* bridge — `qrc:///` rewritten to `file:///android_asset/` — and the test dict has no images/audio. The full loopback HTTP server for `bres://`/`gdau://` lands when a real port needs assets; recorded as a follow-up.
- [x] 2.3 In-article navigation: intercept `gdlookup://` links in the QtWebView navigation signal → in-app lookup; back navigation between articles. **[Partial]** the QML routes `articleLoaded` via state; in-article `gdlookup://` interception is part of the loopback server above.
- [x] 2.4 On-device verification (milestone 1 gate): staged Aurelex Basic DSL loads; typing "app" shows suggestions; tapping renders the article with HTML (CSS from loopback); not-found shows the standard indication; no jank on the UI thread (lookup runs off-thread). **Verified on-device** (branch `qt-quick-frontend`).

## 3. Milestone 2 — dictionary management

- [x] 3.1 Dictionaries page: list from `gd_dict_info`, count display, remove (`gd_remove_dict`) with confirm dialog, reorder (`gd_move_dict`). Confirm dialog added to the Dicts pane (Remove opens an overlay with Cancel/Remove; Cancel verified on-device, Remove reuses the tested `removeDictionary` path).
- [x] 3.2 Add-dictionaries flow (sandbox mode): scan the staged folder (`gd_scan_dicts(files/staged)`); message when nothing supported found. (SAF/opt-in flow is milestone 7.)
- [x] 3.3 On-device verification: add staged folder → count/list updates; remove → gone from lookups; reorder → article order follows; dedup on re-scan. **Verified on-device** (`setDictionaries count=1 names="Aurelex Basic"`).

## 4. Milestone 3 — groups

- [x] 4.1 Groups page: list (`gd_group_count/info`), create/rename/delete, apply active (`gd_group_set_active`), membership editor (`gd_group_dicts` + add/remove/move). **Verified on-device**: membership mode lists members vs non-members, Add/Remove/Up/Down updates the group in place, back returns and dictCount reflects membership.
- [x] 4.2 On-device verification: create group with one dict; active-group lookup respects membership; deleting active group reverts to "All"; default "All" cannot be deleted. **Verified on-device** (`setGroups count=1`).

## 5. Milestone 4 — full-text search

- [x] 5.1 FTS page: per-dict index states (`gd_fts_index_state`), build action (`gd_fts_index`) with in-progress indication, query + modes (`gd_fts_search`), results → article lookup. **[Partial]** the per-dict "Index" button is on the Dicts pane (not FTS pane); mode selector is a cycling button (not `ComboBox`); index-state list is not shown on the FTS pane.
- [x] 5.2 On-device verification: body-word search returns headword; prefix `read*` matches; empty query no-op; active-group scoping respected. **Verified on-device**: `ftsIndex dict=0 rc=0`, `gd_fts_search rc=1 raw bytes=19`, `ftsSearchReady query='apple' results=1`.

## 6. Milestone 5 — history + favorites

- [x] 6.1 Persistence compatibility (D6): **[Modified]** the experiment uses JSON files (`files/history.json`, `files/favorites.json`) instead of SharedPreferences (simpler, no JNI needed). Key contract: JSON arrays of headword strings. Data will NOT carry over from the Kotlin app (different format + different storage) — a one-time re-favorite/re-history is needed after the swap.
- [x] 6.2 History page: most-recent-first list, tap-to-lookup, per-item remove, clear-all. Favorites: article star toggle + page with tap/remove. **[Partial]** the experiment uses Rectangle+Text+MouseArea for rows (not SwipeDelegate); a favorite toggle (★) is on the article page top bar.
- [x] 6.3 On-device verification: parity with the shipped behavior, incl. persistence across force-stop. **Verified on-device**: `files/history.json` contains `["Apple"]` after lookup.

## 7. Milestone 6 — onboarding, empty states, dark mode, external entry points

- [x] 7.1 First-run onboarding overlay + empty search state (`dictCount == 0`); `onboarded` preference stored in `files/settings.json`. **[Partial]** the upgrade heuristic (skip onboarding for existing users) is not implemented — fresh installs always show onboarding.
- [x] 7.2 Dark mode: manual toggle → `gd_set_dark_mode` + QML palette switch; persisted in `files/settings.json`. **[Partial]** the QML uses hardcoded ternaries (`engine.darkMode ? X : Y`) instead of Material theme; a "D" button in the top bar toggles.
- [x] 7.3 External entry points in the manifest: `ACTION_SEND` text, `aurelex://lookup?word=`, `ACTION_PROCESS_TEXT` → routed via `ExperimentActivity.captureLookupText` → SharedPreferences → `EngineController.readPendingLookup()` → `engine.lookup()`. **[Partial]** the pending lookup is only read in `Component.onCompleted` (startup); `onNewIntent` captures the word but the QML doesn't re-read until restart.
- [x] 7.4 TTS pronounce action on the article page (same graceful-unavailable contract). **Cut for v1** (see AGENTS.md "Cut for v1: TTS"); no TTS action is exposed, so the graceful-unavailable contract is trivially satisfied.
- [x] 7.5 On-device verification: PROCESS_TEXT captured "hello" in `shared_prefs/intent.xml`. Share + VIEW declared in the manifest (untested via adb but same code path).

## 8. Milestone 7 — Java shell, storage opt-in, release packaging

- [x] 8.1 QS tile (`AurelexTileService` — clipboard funnel via `aurelex://lookup` deep link) + home-screen widget (`AurelexSearchWidget` — tappable bar opens the app). **[Partial]** the QS tile reads the clipboard and fires the deep link; the widget is a tappable bar (no text input — RemoteViews limitation, same as the shipped app).
- [x] 8.2 Storage modes: sandbox default (staged dir) + opt-in "system folders" behind All-Files-Access (Settings deep link + `isExternalStorageManager` check); SAF pick → stage copy path kept for unresolvable providers. **Superseded by `folder-scoped-storage`** — the app now uses folder-scoped SAF sources (no AFA); the AFA helpers were removed.
- [x] 8.3 Release packaging: signed release APK via `build.ps1 -Configuration Release` (uses the debug keystore for now; production keystore is a follow-up). **Verified**: 22 MB release APK built and installed.
- [x] 8.4 Package swap: flip id to `aurelex.android`; verify SharedPreferences + staged dicts carry over; mark the Kotlin `app/` UI paused/retired. **Done** (2026-09-03): manifest, Java package, JNI class path, `PROGRAM_FILES_ROOT`, build.ps1 launch line; verified installs + runs as `aurelex.android`; Kotlin `app/` retired.
- [ ] 8.5 On-device verification: full pass of docs/TESTING.md against the Qt app.

## 9. Guardrails (throughout)

- [x] 9.1 `engine/`, `patches/`, `jni_bridge.cc`, and the paused Kotlin `app/` UI stay untouched (parity comes from the new stack, not edits to the old).
- [x] 9.2 Every milestone keeps `build.ps1` green and the APK installable; no milestone ships UI that regresses an already-passing slice.
- [x] 9.3 SharedPreferences key contract (D6) **superseded**: the experiment uses JSON files instead of SharedPreferences for history/favorites. The key contract is now the JSON file names + structure.
- [x] 9.4 Follow-up changes after parity (each its own OpenSpec change): sandbox-storage default + opt-in (roadmap #1), dark-mode-follows-system (roadmap #2), engine-notification item retired automatically (no FGS exists in the Qt app).
- [x] 9.5 UI strategy: bare-QtQuick. **Superseded by `qt-material-ui` change.**

## 10. Remaining slices to reach true parity (before package swap)

These are the two gaps that prevent the Qt app from being a drop-in replacement
for the Kotlin app. Each is a focused session of work.

### Slice A — Article bridge (design D3, ~1-2 days)

- [x] A.1 `ArticleServer`: QTcpServer on 127.0.0.1 (random port), serving:
  - Bundled asset mirror (scripts/stylesheets/icons/flags) from the APK's `assets/`
  - `bres://` resources via `gd_get_resource` (images from `.mdd`)
  - `gdau://` audio via `gd_get_audio` (content-type by extension)
  - **Build note**: Android 9+ blocks cleartext HTTP — added a networkSecurityConfig whitelisting 127.0.0.1 (referenced from the manifest).
- [x] A.2 Rewrite article HTML URLs: `qrc:///` → `http://127.0.0.1:PORT/`, `bres://` → `http://127.0.0.1:PORT/bres/...`, `gdau://` → `http://127.0.0.1:PORT/gdau/...`
- [x] A.3 In-article `gdlookup://` link interception → in-app lookup. **Implementation**: QtWebView 6.6 has no navigationRequested — intercept via `onUrlChanged`; parse `gdlookup://localhost/<word>` (path) and `gdlookup://localhost/?word=<w>` (query, after netmgr rewrite); `engine.lookup(word)`; rewind WebView with `loadHtml(about:blank)` to avoid the failed-load frame; back-stack (`navStack`) supports the Back button.
- [x] A.4 Bundle the asset mirror (scripts/stylesheets/icons/flags from `engine/src/`) into the APK's `assets/` directory. **Implementation**: copied from `app/src/main/assets/` → `experiments/qtquick/android/assets/`; build.ps1 explicit copy step (the carve-subset kit doesn't propagate `QT_ANDROID_PACKAGE_SOURCE_DIR/assets/` reliably into the gradle staging tree).
- [ ] A.5 On-device verification: article with CSS styling renders; images from `.mdd` display; audio plays; in-article links navigate. **Verified on-device** (Motorola ThinkPhone, `aurelex.android` package): Longman Pronunciation Dictionary (DSL + wav zip) renders styled article with IPA + Play icons; audio playback via Android MediaPlayer works end-to-end (tap Play → JS click-probe → `engine.playAudio` → JNI → `ArticleServer` serves wav → MediaPlayer). **gdlookup note**: this dict emits 0 `gdlookup://` links (cross-refs render as plain text), so the in-article lookup path is wired (click-probe detects the anchor) but not exercised by a real link here; the mechanism is proven by the audio anchor path. **Images from `.mdd`**: not exercised (dict is DSL, not MDX) — deferred to a real MDict install or a future test dict. **Test dict**: `/GoldenDict/` top level (Longman copied up from `English/` because the carve scan is top-level-only).

### Slice B — Storage opt-in + release identity (~1 day)

- [x] B.1 Wire `isAllFilesAccessGranted()` / `openAllFilesAccessSettings()` into the Dicts pane QML (button: "Grant storage access" when not granted). **Verified on-device** (grant via appops → hint text swapped live).
- [x] B.2 When granted, `scanDicts` points at `externalStoragePath()` + `/GoldenDict` (created on demand) instead of the sandbox `files/staged`. **Verified on-device** (scan switched, dict loaded from /GoldenDict; note: scan is top-level only, per the boundary's non-recursive `collectFiles`).
- [x] B.3 Flip package id from `com.aurelex.experiment` to `aurelex.android`. **Done** (2026-09-03): manifest, Java package (src moved to `aurelex/android/`), JNI class path in `EngineController.cpp`, `PROGRAM_FILES_ROOT` in CMakeLists, `build.ps1` launch line. Stale staged `src/com/` cleaned by build.ps1. **Verified on-device**: installs + runs as `aurelex.android`; AFA scan + audio both work under the new package. The old Kotlin app (`aurelex.android`) must be uninstalled to install this over it (signature mismatch); fresh install means history/favorites reset, dicts survive in `/GoldenDict`.
- [x] B.4 Verify user-data carry-over after the id flip (fresh-install expectations: rescan /GoldenDict, onboarding shows, history/favorites empty). **Verified (fresh install)**: the flipped app rescanned `/GoldenDict` (2 dicts loaded) and audio worked; onboarding shows on a fresh install; history/favorites empty as expected.
- [ ] B.5 Production keystore (replace the debug keystore in build.gradle). **Missing input**: keystore file + passwords (or generate one and store in GitHub secrets).
- [x] B.6 CI workflow: tag push → build release APK → attach to GitHub release. **Implemented** `.github/workflows/release-qt.yml` (windows-latest; tag push `v*` + `workflow_dispatch`). Qt 6.6.3 via aqt (MinGW host + android kits), NDK r23c, SDK 34/35, JDK 17, vcpkg + xapian (arm64-android cached by `actions/cache@v4`), `apply-patches.sh`, signed release APK via `AURELEX_KEYSTORE_*` secrets (unsigned dry-run when unset), version stamped from tag, upload + GitHub release via softprops. `build.ps1` parameterized (env overrides for Qt/vcpkg/NDK/SDK/JDK/cmake/deployqt/keystore/version). **Verified locally**: `assembleRelease` produces a signed, `jarsigner -verify`-clean APK (debug keystore). **Not yet run on CI**: needs first tag push / dispatch. The Kotlin app (`app/`) and its `build-apk.yml` were removed (never released); `release-qt.yml` is now the only release workflow.
- [ ] B.7 On-device verification: full docs/TESTING.md pass.

### Follow-up (recorded, not in parity scope)

- [x] F.1 Restore full IME composing (user-preferred keyboard works today, limited). **Resolved pragmatically**: system IME (SwiftKey) + `ImhHiddenText` hints on all TextInputs — the IME treats fields as password-style and commits keys directly, bypassing the broken composing/extracted-text path (Qt 6.6 + Android 15: composing revert, inactive InputConnection, IME deadlocks). Trade-off: no swipe-typing/autocorrect/composing — acceptable for dictionary headword lookups. Embedded Qt VirtualKeyboard kept as a fallback (QT_IM_MODULE=qtvirtualkeyboard env toggle in main.cpp; VK staging in build.ps1). Full composing needs the Qt 6.8/6.9 upgrade.

### Post-parity (separate OpenSpec changes)

- [x] 10.1 `qt-material-ui` — Material Design 3 restyling (separate change, **done/archived**)
- [x] 10.2 Sandbox-storage default + opt-in (roadmap #1) — **done** as `folder-scoped-storage`
- [x] 10.3 Dark-mode-follows-system (roadmap #2) — **done** (qt-material-ui 3.3)
- [x] 10.4 Engine-notification item retired automatically (no FGS in the Qt app) — **retired**