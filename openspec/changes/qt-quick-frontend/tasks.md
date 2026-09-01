## 1. QML spike scaffold (opt-in, isolated)

- [ ] 1.1 Add an experiment dir (e.g. `experiments/qtquick/`) with a minimal Qt Quick module + one `Activity` subclass wired to load `libaurelex.so` in-process; do **not** wire it into the shipped Gradle build variants.
- [ ] 1.2 Reuse the existing Qt 6.6.3 android kit toolchain path from `app/src/main/cpp/engine/CMakeLists.txt` (read-only reference; the spike has its own CMake that links the same `gd_*` boundary + Qt Quick/WebView).
- [ ] 1.3 Gate 1 — in-process coexistence: a QML `Window` + `QtWebView` running in the **same process** as `libaurelex.so`, with the article bridge (`qrc://`/`bres://`/`gdau://`, `gdlookup://`) intact; verify no HWUI-style blank/rendering crash on the arm64-v8a device (ThinkPhone).

## 2. In-process engine + article bridge

- [ ] 2.1 Load the carve's `gd_*` boundary in-process and run `gd_lookup` on the StarDict/DSL fixture; render the returned HTML through `QtWebView` with the scheme handlers working.
- [ ] 2.2 Re-measure the same smoke fixtures against **both** the current JNI/IPC path and this in-process call, capturing output parity and the latency delta (the bridge-cost artifact).
- [ ] 2.3 Gate 2 — record conclusively whether `QtWebView` handles the custom scheme/bridge identically to the native `WebView` used by the Kotlin UI, or whether parsing quirks appear.

## 3. Java-shell coexistence

- [ ] 3.1 Gate 3 — confirm the QS tile, home-screen widget, and SAF folder flows still function while the QML `QtQuick` UI is the active content (Java window + Qt Quick coexist in one process).

## 4. Decision

- [ ] 4.1 Produce a credible port estimate for the full 1.0 feature set (lookup, dictionaries/groups, FTS, history/favorites/onboarding/empty states, dark mode) plus LGPL/dynamic-linking notes.
- [ ] 4.2 Write the Go/No-Go recommendation into `design.md` (Decision section). Only **Go** if all three gates pass AND the estimate is bounded (weeks, not months).
- [ ] 4.3 Clean up: ensure no spike/experiment artifacts leak into the shipped tree (`git status` clean of it) unless intentionally kept behind the opt-in flag.

## 5. Guardrails (throughout)

- [ ] 5.1 No changes to `engine/`, `patches/`, `jni_bridge.cc`, or the shipped `app/` Kotlin during the experiment.
- [ ] 5.2 The spike is committed only behind an opt-in (never built by default), so the shipped Android app is unaffected.
- [ ] 5.3 The QS tile/widget/SAF Java shell is treated as permanent (thin layer), not to be re-implemented in QML as part of this experiment.