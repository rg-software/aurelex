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

*Pending spike.* Not adopted. Updated by the spike's final task.