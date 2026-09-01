## 1. Xapian bootstrap (native build)

- [ ] 1.1 Confirm whether a `xapian` vcpkg port builds for `arm64-android` and
      `x64-android` on the pinned baseline; record the result.
- [ ] 1.2 If no android port: write a script (under `scripts/`) that builds a
      pinned xapian-core release with the NDK toolchain for each android ABI
      and installs into `${VCPKG_ANDROID_ROOT}` (headers + `libxapian.a`).
- [ ] 1.3 Add the host-side xapian dependency to the engine-smoke CI vcpkg
      install list (x64-windows), matching Dev's local host build.

## 2. Carve CMake + engine sources

- [ ] 2.1 In `app/src/main/cpp/engine/CMakeLists.txt`, swap `fts_stub.cc` for
      `${ENGINE_DIR}/src/ftshelpers.cc` in `AURELEX_CARVE_SOURCES`.
- [ ] 2.2 Delete the boundary `ftshelpers.hh` shadow so the upstream header
      wins the include search.
- [ ] 2.3 Link xapian into `AURELEX_CARVE_LIBS` (per-triplet library name) and
      keep the `ui_fulltextsearch.h` shim for `globalregex.cc`.
- [ ] 2.4 Host smoke build (Windows): configure + compile the carve with xapian
      linked; resolve any header/port issues from removing the shadow header.

## 3. Boundary C API

- [ ] 3.1 Declare `gd_fts_index`, `gd_fts_index_state`, `gd_fts_search` in
      `goldendict.h` with the documented return codes.
- [ ] 3.2 Implement them in `gd_boundary.cc`:
      - `gd_fts_index(dict_index)` → `dict->makeFTSIndex(...)`; return 0/-1.
      - `gd_fts_index_state(dict_index, &out)` → 0 present / 1 missing / error.
      - `gd_fts_search(query, mode, group_id, &out, size)` → run
        `FtsHelpers::FTSResultsRequest` for the group's dicts, serialize
        matching headwords (+ dict id) newline-delimited, like `gd_suggest`.
- [ ] 3.3 Ensure `gd_fts_search` wraps the async request with a bounded wait and
      returns -3 when a dictionary has no full-text index yet.

## 4. Android JNI + IPC

- [ ] 4.1 Add `nativeFtsIndex`, `nativeFtsIndexState`, `nativeFtsSearch` to
      `jni_bridge.cc` + `NativeEngine.kt` (mirroring existing group methods).
- [ ] 4.2 Add opcodes `OP_FTS_INDEX`, `OP_FTS_INDEX_STATE`, `OP_FTS_SEARCH` to
      `EngineService.kt` + `EngineClient.kt` with the `fts*` Future API
      (`callInt` / `callBytes`) and a `callIntArray`/string parse.
- [ ] 4.3 Verify an end-to-end JNI→service→client round-trip builds (Kotlin
      compiles; native lib links).

## 5. ViewModel + UI

- [ ] 5.1 Add FTS state to `MainViewModel`: `_ftsResults`,
      `_ftsIndexStates` (per-dict index-state map), `_ftsBuilding` flags; add
      `ftsSearch(query, mode)`, `ftsIndex(dictIndex)`, `ftsState(dictIndex)`.
- [ ] 5.2 Add a `Dest.FTS` + `FtsScreen` (query field, mode selector, index
      status list, results list) wired into `MainActivity.kt`; results rows tap
      through `viewModel.lookup(headword)`.
- [ ] 5.3 Surface the per-dictionary index state ("built / building / missing")
      and trigger index build on demand with an in-progress indication.
- [ ] 5.4 Reuse active-group lookup: results run against the active group;
      entry point appears on the search screen.

## 6. Verification (host + device)

- [ ] 6.1 Host smoke: extend `smoke/main.cpp` to index the StarDict fixture,
      run `gd_fts_search("smoke")`, assert the headword is returned; update
      `engine-smoke.yml` assertion.
- [ ] 6.2 Build the android APK; install on Motorola ThinkPhone.
- [ ] 6.3 Load a dictionary, run a plain-text FTS query that matches a body
      word (e.g. a term inside an article, not a headword); expect the article's
      headword as a result and that tapping it opens the article.
- [ ] 6.4 Verify index state shows built/missing; first search builds the index
      then returns results; rescan rebuilds a stale index.
- [ ] 6.5 Verify search modes (plain text / wildcard / regexp), empty-query
      handling, and that a result respects the active group.

## 7. Wrap-up

- [ ] 7.1 Update ROADMAP.md (flip full-text search from planned to in progress,
      then done), and archive the change at completion.