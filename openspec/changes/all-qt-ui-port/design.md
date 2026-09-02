## Design

### Context

The `qt-quick-frontend` experiment (branch `qt-quick-frontend`, design.md there)
proved: engine + QML + QtWebView in one process (Gate 1), the full in-process
lookup pipeline (`gd_init` → `gd_scan_dicts` → `gd_lookup` → rendered HTML,
Gate 2), and Java-shell coexistence (QS tile bound by SystemUI into the same pid,
Gate 3). Tooling facts established there: `qt_add_apk_target` is absent from the
aqt carve-subset install → package via `androiddeployqt` + generated deployment
settings; `ANDROID_PLATFORM=android-30` (NDK r23c); NDK bionic include needed for
`iconv.h`; Gradle must run under JDK 17; aapt2 needs compileSdk `android-34`.

See `openspec/changes/qt-quick-frontend/design.md` — not restated here.

### Goals / Non-Goals

**Goals:**
- One Qt process app with full v1 feature parity, built and verified in slices.
- Direct C++ calls from QML controller classes (no `gd_*` round-trips needed where
  the boundary is thin, but the `gd_*` C API stays the integration surface — it is
  stable, testable, and already smoke-covered).
- Keep user data (SharedPreferences keys) and dictionary staging compatible so the
  final package swap is seamless.
- Every milestone ends with a buildable APK and an on-device verification step.

**Non-Goals:**
- Removing the Kotlin app / `EngineService` / `jni_bridge` (paused until parity).
- Roadmap behavior changes (sandbox-storage default, dark-mode-follows-system) —
  separate follow-up changes after the port.
- Qt WebEngine (Play-hostile, huge); article rendering stays on Android WebView
  via `QtWebView`.
- iOS or desktop targets.

### Decisions

**D1 — The experiment app is the port vehicle.** Grow `experiments/qtquick` in
place (package `com.aurelex.experiment`, opt-in build) rather than forking a new
module; at parity, flip the package id to `aurelex.android` and retire `app/`.
Alternative considered: a parallel `app-qt/` module from day one — rejected:
duplicates the carve wiring for no benefit while the Kotlin app is paused.

**D2 — QML ↔ engine via a C++ controller layer, not raw `gd_*` in QML.** A
`EngineController` QObject (singleton via QML context property / qmlRegisterSingleton)
exposes async signals + Q_PROPERTY for: suggestions, article HTML, dict list,
groups, FTS state/results, history/favorites, dark mode. Internally it calls the
`gd_*` C API on a worker thread (the boundary blocks on the calling thread) and
emits results as signals. QML stays declarative and never blocks the UI thread.
Alternative considered: exposing every `gd_*` function directly — rejected:
blocking calls in QML would jank the render thread.

**D3 — Article bridge = local loopback HTTP server.** `QtWebView` cannot
intercept custom schemes. Instead of URL rewriting hacks, run a tiny HTTP server
(`QTcpServer`, 127.0.0.1, random port) inside the app that serves:
- `qrc:///`-equivalent assets from the bundled asset mirror (scripts, stylesheets,
  icons, flags),
- `bres://` resources via `gd_get_resource`,
- `gdau://` audio via `gd_get_audio` (content-type by extension).
The article HTML's URLs are rewritten once (qrc/bres/gdau → `http://127.0.0.1:PORT/…`)
before `loadHtml`. In-article `gdlookup://` links stay custom and are intercepted
via the WebView's `loadingChanged`/navigation signal → in-app lookup (same
behavior as the Kotlin `shouldOverrideUrlLoading`). Audio playback goes through
`QMediaPlayer` or is handed to the Android player as today.
Alternative considered: pre-extracting resources to files — rejected: unbounded
disk churn per article; the loopback server is ~200 lines and matches upstream's
request semantics.

**D4 — Sliced milestones, each shippable to the device.** Seven slices (see
proposal). Each ends with: QML page(s) + controller methods + an on-device
verification checklist item in tasks.md. No slice breaks the previous one; the
experiment's core-lookup flow is milestone 1.

**D5 — Packaging script, not interactive.** The build/deploy sequence
(cmake → ninja → androiddeployqt → gradle assembleDebug) is wrapped in one
PowerShell script (`experiments/qtquick/build.ps1`) that encodes the toolchain
facts (Qt paths, ANDROID_PLATFORM=android-30, JDK 17 for gradle, the
gradle.properties/local.properties overrides after each androiddeployqt run —
the deploy regenerates them). CI reuses it later.

**D6 — Persistence compatibility.** `PreferencesStore` keys (`darkMode`,
`ttsEnabled`, `history`, `favorites`, `scanPath`, `onboarded`) are reproduced
exactly (via JNI `SharedPreferences` access from C++, or a small Java helper
class in the shell) so the final package swap preserves user data. Dict staging
dir (`files/staged`) and `scanPath` semantics stay identical.

**D7 — Dark mode in this port = manual toggle only** (engine `gd_set_dark_mode`
+ QML palette), matching current behavior; system-follow lands as the roadmap
follow-up change.

### Risks / Trade-offs

- [QtWebView feature gaps vs Android WebView API (e.g. file chooser, text
  selection menus)] → Milestone 1 verifies the article use cases; gaps get
  documented and, if blocking, handled via the Java shell (a thin
  WebView-in-Qt-window hybrid is the escape hatch, same pattern as Gate 3).
- [Loopback server port/security] → Bind 127.0.0.1 only, random port, no
  external exposure; resources are served only to the app itself.
- [Blocking `gd_*` calls stall UI] → All controller calls on worker threads
  (D2); lookup/scan already bounded internally.
- [Preference drift between apps during transition] → D6 keys frozen; a tiny
  shared doc lists the key contract.
- [CI complexity for Qt android builds] → Defer to milestone 7; local
  build.ps1 is the source of truth for the recipe.

### Migration Plan

Slices 1–6 develop the QML app under `com.aurelex.experiment` (sideload only).
Slice 7: flip package id to `aurelex.android`, verify user-data carry-over
(SharedPreferences + staged dicts survive an install-over or a documented
one-time re-stage), wire CI release, archive the Kotlin UI as paused. Rollback
at any point = keep shipping the paused Kotlin app (untouched).

### Open Questions

- Audio: `QMediaPlayer` with a loopback URL vs handing bytes to the Android
  MediaPlayer via JNI (current approach). Resolve in milestone 1/6 by testing
  the loopback path first (simplest).
- `QtWebView` selection/copy menu behavior for dictionary text — verify in
  milestone 1; if unusable, evaluate the hybrid escape hatch.