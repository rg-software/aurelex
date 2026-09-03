## Why

The app's complexity is dominated by the forced separation between a Kotlin/Compose
UI and a C++ engine. That separation exists only because real Qt 6 cannot share a
process with Compose/WebView without breaking HWUI rendering (commit `2b106f2`),
which forced a `:engine` process, a JNI/C boundary, Messenger IPC, `resumeScan`
self-heal, and a confusing foreground-service notification. This change explores
the most direct resolution: **drop the Kotlin/Compose UI entirely and build the
whole app as a Qt-for-Android Qt Quick (QML) app**, so the engine and UI live in
one process and the entire client/server seam is deleted by construction.

It is an **experiment with a decision as its deliverable** — a cheap QML spike to
validate the only genuinely uncertain pieces, with a Go/No-Go recommendation; no
feature ships and nothing in the shipped app changes.

## What Changes (experiment scope)

- **Minimal Qt Quick spike on the existing toolchain**: the repo already
  cross-compiles Qt 6.6.3 android kits (arm64+x86_64) via `aqt` (spike evidence),
  so stand up a tiny QML Activity that loads `libaurelex.so` in-process and does
  one dictionary lookup rendered via `QtWebView` (wraps Android's native WebView —
  same in-process article bridge, no HWUI clash). Deliberately **not** Qt WebEngine
  (huge, Play-hostile).
- **Prove the three unknowns only**: (a) in-process engine + QML Activity coexist
  on this kit without HWUI crash; (b) `QtWebView` renders `gd_lookup`-style HTML
  with the `qrc://`/`bres://`/`gdau://` bridge working; (c) a thin Java shell can
  still host the Quick Settings tile / home-screen widget / SAF while the real UI
  is QML.
- **Output**: maximize-scope/impact estimate for the full 1.0 feature set port
  (lookup, dictionaries, groups, FTS, history/favorites/onboarding/empty states,
  dark mode), plus LGPL/dynamic-linking notes. Decision: **pursue the all-Qt port**
  (single-process, no boundary/IPC/FGS) or **reject** it in favor of the current
  Kotlin+`:engine` architecture (or the confined-shim path, evaluated separately in
  `confined-qt-shim`).

No shipped app code changes in this change. If adopted, the actual port is a
separate (large) implementation change with specs.

## Capabilities

### New Capabilities

None — `skip_specs` (experiment only). If adopted, the port change carries the specs.

### Modified Capabilities

None.

## Impact

- **New, isolated**: a spike scaffold (a minimal QML module + one `Activity`
  subclass) added under a dedicated experiment dir, opt-in, not wired into the
  shipped build.
- **Reuses, does not modify**: `libaurelex.so` / `gd_*` boundary, the Qt 6 android
  kit path in `CMakeLists.txt` (audited read-only for the spike), the existing
  asset mirror + article bridge logic.
- **No changes** to the shipped `app/` Kotlin UI, `patches/`, or `engine/` during
  the experiment.
- **If adopted later (out of scope here)**: the Compose UI tree is replaced by QML
  and the `:engine` process / JNI / Messenger / FGS notification are removed; a
  thin Java shell remains for launcher surfaces. That is the follow-up change with full specs.