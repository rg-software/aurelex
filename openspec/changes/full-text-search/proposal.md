## Why

Headword lookup only finds words the dictionary author indexed as entries.
Power users constantly need to find a word *inside* article bodies — the
definition text contains a term that is not its own headword. Upstream
goldendict-ng solves this with full-text search (FTS) over a Xapian index.
Aurelex cut FTS for v1 (design D6) by stubbing the entire FTS surface
(`fts_stub.cc`, a shadow `ftshelpers.hh`, a shim `ui_fulltextsearch.h`); this
change reinstates it on Android.

## What Changes

- **Re-enable the engine's Xapian FTS backend in the carve.** The carve
  currently compiles `fts_stub.cc` (no-op index + empty results) and shadows
  the upstream `ftshelpers.hh`. This change compiles the real upstream
  `engine/src/ftshelpers.cc` (index build + query) and lets the dict backends
  (StarDict/DSL/mdx) use their existing `FtsHelpers::*` calls as upstream
  intends. The upstream `fulltextsearch.cc` (Qt Widgets dialog) stays out —
  it is desktop UI.
- **Cross-compile xapian-core for Android** and link it into `libaurelex.so`
  (new native dependency; touches the merge contract / CI, see Impact).
- **New boundary C API `gd_fts_*`**: build/check a dictionary's full-text
  index and run a full-text search returning matched headwords (each result
  maps to a normal article lookup). Drives the same `FtsHelpers` surface the
  upstream dialog uses.
- **FTS UI (Kotlin/Compose)**: a full-text search screen with a query box,
  the four upstream search modes (whole words / plain text / wildcards /
  regexp), a per-dictionary index-status + progress surface, and a results
  list whose taps open the standard article.
- **Search modes** mirror upstream `FTS::SearchMode` (Xapian query syntax,
  plain text, wildcards, regexp).

## Capabilities

### New Capabilities
- `full-text-search`: Searching the article bodies of loaded dictionaries by
  building and querying a per-dictionary on-device index, and presenting the
  matching headwords as lookup results.

### Modified Capabilities
- none

## Impact

- **Merge contract:** reinstating FTS removes one carved stub and adds a real
  upstream source (`engine/src/ftshelpers.cc`) to the carve plus a new native
  dependency (xapian). This is a dependency + boundary change, so it goes
  through the patch pipeline and CI smoke must assert FTS works.
- **Native builds:**
  - `app/src/main/cpp/engine/CMakeLists.txt` — swap `fts_stub.cc` for
    `${ENGINE_DIR}/src/ftshelpers.cc`; drop the shadow `ftshelpers.hh` (real
    upstream header must win); link xapian; keep the `ui_fulltextsearch.h`
    shim (still needed by `common/globalregex.cc`).
  - `app/src/main/cpp/engine/goldendict.h` + `gd_boundary.cc` — `gd_fts_*`
    exports.
  - New cross-compiled Android build of xapian-core (via the existing vcpkg
    android triplet or a build step if no android port exists upstream).
- **CI:** `.github/workflows/engine-smoke.yml` and `build-apk.yml` must install
  xapian and add an FTS assertion (index "smoke" dict, search a body word,
  expect the headword) so the smoke gate catches regressions.
- **Android boundary/IPC:** `jni_bridge.cc`, `NativeEngine.kt`,
  `EngineService.kt`, `EngineClient.kt` grow `fts*` opcodes/calls.
- **UI/Kotlin:** `MainViewModel.kt` + `MainActivity.kt` for the FTS screen,
  index status/progress, and results → article navigation.
- **Docs:** design D6 in the archive is superseded; ROADMAP milestone flips.

## Risks (summary)

- Xapian-on-Android availability via vcpkg is the biggest unknown (may need a
  custom build). See design.md for the concrete plan and fallbacks.
- Index build time on device for large dictionaries; mitigated by
  per-dictionary lazy indexing and a visible progress state.