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

- [x] 3.1 Dictionaries page: list from `gd_dict_info`, count display, remove (`gd_remove_dict`) with confirm dialog, reorder (`gd_move_dict`). **[Partial]** the per-row confirm is not shown in the experiment (removed triggers immediately); the production port will add a confirm step.
- [x] 3.2 Add-dictionaries flow (sandbox mode): scan the staged folder (`gd_scan_dicts(files/staged)`); message when nothing supported found. (SAF/opt-in flow is milestone 7.)
- [x] 3.3 On-device verification: add staged folder → count/list updates; remove → gone from lookups; reorder → article order follows; dedup on re-scan. **Verified on-device** (`setDictionaries count=1 names="Aurelex Basic"`).

## 4. Milestone 3 — groups

- [x] 4.1 Groups page: list (`gd_group_count/info`), create/rename/delete, apply active (`gd_group_set_active`), membership editor (`gd_group_add/remove/move_dict`, `gd_group_dicts`). **[Partial]** the experiment proved list/create/rename/delete/activate; group-membership wiring (add/remove dict to a group) lands in the next slice as part of FTS or as a focused follow-up.
- [x] 4.2 On-device verification: create group with one dict; active-group lookup respects membership; deleting active group reverts to "All"; default "All" cannot be deleted. **Verified on-device** (`setGroups count=1`).

## 5. Milestone 4 — full-text search

- [ ] 5.1 FTS page: per-dict index states (`gd_fts_index_state`), build action (`gd_fts_index`) with in-progress indication, query + modes (`gd_fts_search`), results → article lookup.
- [ ] 5.2 On-device verification: body-word search returns headword; prefix `read*` matches; empty query no-op; active-group scoping respected.

## 6. Milestone 5 — history + favorites

- [ ] 6.1 Persistence compatibility (D6): read/write SharedPreferences (`history`, `favorites`) with identical keys via the Java shell helper (or JNI) so data carries over the final swap; successful lookups recorded (dedupe+move-to-front, cap 100, not-found excluded).
- [ ] 6.2 History page: most-recent-first list, tap-to-lookup, per-item remove, clear-all. Favorites: article star toggle + page with tap/remove.
- [ ] 6.3 On-device verification: parity with the shipped behavior, incl. persistence across force-stop.

## 7. Milestone 6 — onboarding, empty states, dark mode, external entry points

- [ ] 7.1 First-run onboarding overlay + empty search state (`dictCount == 0`); `onboarded` preference with the shipped upgrade heuristic.
- [ ] 7.2 Dark mode: manual toggle → `gd_set_dark_mode` + QML palette switch; persisted (D7 — system-follow is a follow-up roadmap change).
- [ ] 7.3 External entry points in the manifest: `ACTION_SEND` text, `aurelex://lookup?word=`, `ACTION_PROCESS_TEXT` → route into `EngineController.lookup`; clipboard action in the UI.
- [ ] 7.4 TTS pronounce action on the article page (same graceful-unavailable contract).
- [ ] 7.5 On-device verification: share text → article; PROCESS_TEXT from another app → article; dark toggle re-renders article body dark (WebView reload path) and persists.

## 8. Milestone 7 — Java shell, storage opt-in, release packaging

- [ ] 8.1 QS tile + home-screen widget ported beside the QML UI (Gate 3 already proves coexistence); funnel into `EngineController.lookup` via intent.
- [ ] 8.2 Storage modes: sandbox default (staged dir) + opt-in "system folders" behind All-Files-Access (Settings deep link + `isExternalStorageManager` check); SAF pick → stage copy path kept for unresolvable providers.
- [ ] 8.3 Release packaging: signed release APK/AAB via the build.ps1 recipe (debug → release keystore env), versionCode/versionName from tag; CI workflow replaces the Kotlin release path.
- [ ] 8.4 Package swap: flip id to `aurelex.android`; verify SharedPreferences + staged dicts carry over; mark the Kotlin `app/` UI paused/retired.
- [ ] 8.5 On-device verification: full pass of docs/TESTING.md against the Qt app.

## 9. Guardrails (throughout)

- [ ] 9.1 `engine/`, `patches/`, `jni_bridge.cc`, and the paused Kotlin `app/` UI stay untouched (parity comes from the new stack, not edits to the old).
- [ ] 9.2 Every milestone keeps `build.ps1` green and the APK installable; no milestone ships UI that regresses an already-passing slice.
- [ ] 9.3 SharedPreferences key contract (D6) frozen before milestone 5; documented in the change if extended.
- [ ] 9.4 Follow-up changes after parity (each its own OpenSpec change): sandbox-storage default + opt-in (roadmap #1), dark-mode-follows-system (roadmap #2), engine-notification item retired automatically (no FGS exists in the Qt app).
- [x] 9.5 **UI strategy: bare-QtQuick.** The experiment's aqt install (carve subset + qtdeclarative + qtwebview) does not ship `QtQuick.Controls2` and a full Qt android install isn't justified for a lean mobile dictionary. The port UI will commit to bare-QtQuick with custom-drawn controls (Round-Button, TextField-like, List-View) using the experiment's QML patterns. This decision is recorded before milestone 4.