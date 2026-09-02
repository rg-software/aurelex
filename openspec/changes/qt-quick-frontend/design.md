## Decision

### On-device results (2026-09-02, ThinkPhone, branch `qt-quick-frontend`)

- **Gate 1 — in-process coexistence: PASS.** The all-Qt APK (`com.aurelex.experiment`)
  loads `libaurelex_exp` (carve + Qt Core/Gui/Qml/Quick/WebView + platform/webview
  plugins) into **one process** (pid observed; no `:engine`, no JNI, no Messenger,
  no FGS notification). No HWUI blank/crash; Activity displayed in ~290ms.
- **Gate 2 — article bridge: PASS (with rewrite).** `EngineController.rewriteArticleUrls`
  rewrites `qrc:///` → `file:///android_asset/`; `QtWebView.loadHtml` renders the
  engine's article HTML (verified for the "apple" entry: 2892 bytes). Bbres://gdau
  / image resources land in the loopback HTTP-server milestone (design D3); the test
  dict has none, so the rewrite is enough to demonstrate the pipeline.
- **Gate 3 — Java-shell coexistence: PASS.** A `ProbeTileService` (mirror of the
  shipped `QuickLookupTileService` shape) was registered; `cmd statusbar add-tile`
  bound it in **the same process (31282)** as the QML Activity + engine.

### Milestones 1, 2, 3 proven on-device (commit log on `qt-quick-frontend`)

- **Milestone 1 — core lookup**: `EngineController` (QObject, QtConcurrent off-thread)
  exposes `gd_init`/`gd_scan_dicts`/`gd_lookup`/`gd_suggest`/`gd_dict_count`/
  `gd_set_dark_mode`-style helpers and the `qrc:///` rewrite. Single `Window` (bare
  QtQuick — no `QtQuick.Window` import, no `QtQuick.Controls2`) hosts a `TextInput`
  + debounced suggestion `ListView` and a `WebView`; switching to the article
  view is state-based. Verified: `init rc=1`, `scan -> 1`, `gd_lookup("apple") -> 2892`,
  `WebView loading: true, file:///android_asset/`.
- **Milestone 2 — dictionaries page**: added `refreshDictionaries`,
  `removeDictionary(int)`, `moveDictionary(int, int)`. Top-bar cycle button
  search → dicts → groups → search. Dicts pane is a `ListView` whose model is
  `engine.dictionaries` (QVariantList of maps). Verified: `setDictionaries count= 1
  names="Aurelex Basic"`.
- **Milestone 3 — groups page**: added `refreshGroups`, `createGroup`,
  `renameGroup`, `deleteGroup`, `setActiveGroup`. Groups pane has a `TextInput`
  for new-group names and per-row Active / Rename / Delete buttons. Verified:
  `setGroups count= 1` (implicit "All" group, `activeGroupId=0`) before and after
  scan; engine round-trips on every refresh.

### Tooling facts the experiment confirmed

- aqt's android arm64 6.6.3 **carve subset** install lacks `qtquickcontrols2` (and the
  base `QtQuick.Controls2` QML plugin + the `QtQuick.Window` separate import are
  fragile in the aqt build). The experiment works in **bare `QtQuick` +
  `QtWebView`**. The port UI design must pick one:
  - *Use full Qt android (proper `QtQuick.Controls2`)* — bigger install, full
    desktop-like UI, more widgets.
  - *Commit to bare-QtQuick for the port UI* — smaller, leaner, needs custom
    drawn controls (Round-Button, Text-Field-like, List-View etc.). Fits the
    "lean mobile dictionary" story well; the current experiment is already
    doing this.
- `qt_add_apk_target` is absent from the aqt install, so packaging is
  `androiddeployqt --no-build` (which still generates the gradle project) +
  gradle assemble. Works once `local.properties`/`gradle.properties` overrides
  are re-applied after each deploy (`build.ps1` does this).
- `NdkRoot=android-ndk-r23c`, `ANDROID_PLATFORM=android-30` (r23c caps at 33), JDK
  17 for Gradle, AGP 7.4.1 + aapt2 build-tools 35 + compileSdk `android-34` —
  recorded in `build.ps1` / `gradle.properties`.

### Port cost estimate (full v1 parity, in slices)

Sliced milestones 1–3 are **done in the experiment** (~330 LoC of C++ + ~330 LoC
of QML + a ~110-line build script). They prove the in-process pattern, the
worker-thread pattern, the QML ViewModel/Controller split, and the build pipeline.
The remaining work is mechanical porting, not architecture.

Approximate remaining cost (engineering days, single contributor):

| Milestone | Work | Est. days |
| --- | --- | --- |
| 4 — FTS screen | `gd_fts_index`/`gd_fts_index_state`/`gd_fts_search` + results → article lookup; index-state list per dict | 2 |
| 5 — History + favorites | `PreferencesStore` keys compatibility (history, favorites, darkMode, ttsEnabled) + a small Java helper for `SharedPreferences` from C++ *or* move the data store into the engine; on-device test for persistence across force-stop | 2 |
| 6 — Onboarding + empty states + dark mode + share/clipboard/PROCESS_TEXT | Reuse the QML model: `gd_dict_count == 0` empty state, `engine.dictCount == 0` onboarding, dark mode toggle (`gd_set_dark_mode` + QML palette), share/process_text entry points routing to `engine.lookup` | 2 |
| 7 — Java shell + storage + release | QS tile + home-screen widget + SAF opt-in; full release pipeline (CI gradle for Qt android app, signed APK/AAB), flip package id to `aurelex.android` and retire Kotlin `app/` | 4 |
| Polish | Replace the `build.ps1` ad-hoc build with a proper Gradle task wired into CI; remove the `com.aurelex.experiment` package id and migrate to `aurelex.android`; CI release workflow | 2 |
| **Total** | | **12** |

This is a **bounded** port (≈ 12 engineering days, not "months"). The "expensive"
parts (Qt-in-Compose HWUI, separate `:engine` process, FGS notification,
shared-scheme intercept) are gone — they were the load-bearing complexity in the
old architecture, and the experiment confirmed the all-Qt path dissolves them.

**Recommendation: GO on the all-Qt direction.** Begin the `all-qt-ui-port` change
implementation. The remaining work is mechanical; the architecture is decided.

### Constraints / known-ugly bits to call out in the port implementation

- **No `QtQuick.Controls2` on the experiment's aqt install.** Pick a UI strategy
  (bare-QtQuick vs full Qt android) before milestone 4, or the milestones
  after 4 will rebuild the form widgets.
- **`AndroidManifest.xml` needs a `QT_ANDROID_BUNDLED_RESOURCES` flag set right
  for the aqt-deployed path** so the `qml/` + `assets/` get staged into the APK.
  `build.ps1` already runs `androiddeployqt` with `--gradle` and `--no-build` and
  copies the `.so` to the gradle project's `jniLibs.srcDirs`; on a real port, the
  AGP build should run from inside the cmake `add_subdirectory` chain.
- **The shipped `PreferencesStore` Java helper** needs a C++ analog (or a JNI
  bridge to read SharedPreferences). Milestone 5 must commit to one.
- **Article bridge for `bres://` / `gdau://` / real `qrc:///` assets** lands in
  milestone 7 (or a dedicated D3 follow-up). Until then, image/audio-bearing
  dictionaries will look unstyled in the WebView.