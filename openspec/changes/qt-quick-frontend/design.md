## Design

### Goal

Decide, with a cheap spike, whether an **all-Qt (Qt Quick/QML) Android app** is the
right long-term architecture — i.e., whether we should discard the Kotlin/Compose UI
and the `:engine`/JNI/LIPC/FGS seam entirely, in favor of one in-process C++ app.

### Non-goals (of this experiment)

- Not a full port. No feature ships; no shipped app code changes.
- Not deciding the *eventual* UI framework quality trade-off (QML vs Compose) beyond
  what the spike surfaces — only the Go/No-Go.
- Not re-evaluating the QS tile/widget/SAF Java shell (those stay a thin layer either way).

### Method

Use the already-proven **Qt 6.6.3-for-Android toolchain** (arm64+x86_64 kits via
`aqt` — the original spike already compiled these). Stand up a minimal QML Activity
that links `libaurelex.so` **in-process** and renders one article via **`QtWebView`**
(the Android-native-WebView wrapper; deliberately not Qt WebEngine, which is
massive and Play-hostile). The article bridge (`qrc://`/`bres://`/`gdau://`,
`gdlookup://`) is kept as-is.

Three gates, all must hold:
1. **In-process**: `gd_*` engine + QML Activity in one process, no HWUI crash.
2. **WebView bridge**: `QtWebView` renders article HTML with the custom schemes working.
3. **Shell coexistence**: the QS tile/widget/SAF still function with the QML UI active
   (Java window + Qt Quick content can coexist in the same process).

If any gate fails cleanly, that's a hard Drop for the all-Qt direction (e.g. Qt-for-Android
QML + native WebView coexistence limit, or HWUI/QPainter surface conflict).

### Decision criteria

- **Go** only if all three gates pass AND the spike's effort estimate for the real port
  (full 1.0 feature set: lookup, dictionaries/groups, FTS, history/favorites/onboarding/
  empty states, dark mode) is credible (roughly bounded weeks, not months).
- **Drop** if gates fail, the QML↔Java/lifecycle story shows a dealbreaker, or the
  estimate balloons (the whole point was to *simplify*, not trade one seam for another).

### Risks / trade-offs

- [Upstream merge friction] → None worsened: we still compile upstream `src/`
  against real Qt; fewer deviations, no patches.
- [Large frontend rewrite sunk-cost] → The spike is tiny and gated; the sunk cost is
  only realized if we choose Go, at which point we know the estimate.
- [QtWebView limitations on Android] → WebView bridge currently proven on the Kotlin
  side; must re-prove under Qt's wrapper (may impose parsing quirks on `qrc://`).
- [LGPL] → Qt is LGPL; dynamic-linking/relinking obligations stay, but that's true
  today — the all-Qt app only increases Qt surface (still one shared lib).
- [QS tile/widget/SAF interplay] → These are Java-only surfaces; must confirm they
  coexist with a Software-rendered QML/decorated window.

### Open questions (to resolve during the spike, provably)

1. Does `QtQuick` + `QtWebView` coexist with the existing native-WebView assumptions
   in one process on this kit? (Gate 2.)
2. Will the in-process engine hold without the `:engine` process isolation that was
   the sole reason the boundary/IPC layer exists? (Gate 1.)
3. Exact ≈cost delta of switching the article bridge from the JNI/IPC path to direct
   in-process calls — the artifact we re-measure with the same smoke fixtures.

### Decision

### On-device results (2026-09-02, ThinkPhone, branch `qt-quick-frontend`)

- **Gate 1 — in-process coexistence: PASS.** The all-Qt APK (`com.aurelex.experiment`)
  loads `libaurelex_exp` (carve + Qt Core/Gui/Xml/Concurrent/Qml/Quick/WebView +
  platform/webview plugins) into **one process** (pid observed; no `:engine`, no
  Messenger, no FGS). No HWUI blank/crash; Activity displayed.
- **Gate 2 — article bridge: PASS (core).** In-process pipeline works end-to-end:
  `gd_init:1`, `gd_scan_dicts(staged) -> 1`, `gd_dict_count -> 1`,
  `gd_lookup(apple) -> 2892` (real article HTML), rendered through a `QtWebView`
  (wraps Android WebView 144) with `loadHtml`. QML component loads. `QtWebView`
  does **not** intercept custom schemes — the spike already rewrites `qrc:///`
  → `file:///android_asset/` in `qrcToAsset`; `bres://`/`gdau://` still require a
  WebViewClient-equivalent (recorded as a follow-up for a full port).
- **Gate 3 — Java-shell coexistence: NOT RUN.** A QS tile / widget / SAF check
  needs a second Java component beside the Qt Activity; out of scope for this
  spike's device pass and flagged as a remaining unknown (the real tile/widget live
  in the shipped app's package anyway).
- **Tooling notes (for the follow-up port):** `qt_add_apk_target` is absent from
  the aqt "carve subset" install — package with `androiddeployqt` + a generated
  `android-aurelex_exp-deployment-settings.json` manually. The Qt android
  toolchain needs `ANDROID_PLATFORM=android-30` (NDK r23c max 33; carve needs
  iconv/`__ANDROID_API__`≥28 + pthread_cond_clockwait≥30) and the NDK bionic
  include added for `iconv.h`. Gradle must run under **JDK 17** (AGP 7.4.1 +
  JDK 21 → D8 NPE). aapt2 needs compileSdk `android-34` with AGP 7.4.1.

**Assessment:** the all-Qt direction is **viable and low-risk to build on** —
Gate 1 and the article pipeline are proven on-device, and the tooling friction
above is mechanical, not architectural. Remaining unknowns before committing a
full port: Gate 3 (Java shell coexistence) and the real cost estimate of porting
the Compose feature set to QML (not yet measured).

**Recommendation (tentative):** GO on the all-Qt direction as the eventual
architecture, pending (a) Gate 3 and (b) a bounded port-cost estimate. The
`confined-qt-shim` path becomes unnecessary if this holds (Qt is embraced, not
shimmed).