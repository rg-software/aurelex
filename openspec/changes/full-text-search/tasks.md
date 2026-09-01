## 1. Xapian bootstrap (native build)

- [x] 1.1 Confirm whether a `xapian` vcpkg port builds for `arm64-android` and
      `x64-android` on the pinned baseline; record the result.
      Recorded in design.md (Risks): the stock port fails on the pinned
      baseline for both android triplets when the NDK path contains spaces
      (autoconf word-splits the CC path); D2's scripted fallback is the path.
- [x] 1.2 If no android port: write a script (under `scripts/`) that builds a
      pinned xapian-core release with the NDK toolchain for each android ABI
      and installs into `${VCPKG_ANDROID_ROOT}` (headers + `libxapian.a`).
      `scripts/build-xapian-android.sh` (validated for both ABIs, with `-fPIC`).
- [x] 1.3 Add the host-side xapian dependency to the engine-smoke CI vcpkg
      install list (x64-windows), matching Dev's local host build.

## 2. Carve CMake + engine sources

- [x] 2.1 In `app/src/main/cpp/engine/CMakeLists.txt`, swap `fts_stub.cc` for
      `${ENGINE_DIR}/src/ftshelpers.cc` in `AURELEX_CARVE_SOURCES`.
- [x] 2.2 Delete the boundary `ftshelpers.hh` shadow so the upstream header
      wins the include search.
- [x] 2.3 Link xapian into `AURELEX_CARVE_LIBS` (per-triplet library name) and
      keep the `ui_fulltextsearch.h` shim for `globalregex.cc`.
- [x] 2.4 Host smoke build (Windows): configure + compile the carve with xapian
      linked; resolve any header/port issues from removing the shadow header.

## 3. Boundary C API

- [x] 3.1 Declare `gd_fts_index`, `gd_fts_index_state`, `gd_fts_search` in
      `goldendict.h` with the documented return codes.
- [x] 3.2 Implement them in `gd_boundary.cc`:
      - `gd_fts_index(dict_index)` → `dict->makeFTSIndex(...)`; return 0/-1.
      - `gd_fts_index_state(dict_index, &out)` → 0 present / 1 missing / error.
      - `gd_fts_search(query, mode, group_id, &out, size)` → run
        `FtsHelpers::FTSResultsRequest` for the group's dicts, serialize
        matching headwords (+ dict id) newline-delimited, like `gd_suggest`.
- [x] 3.3 Ensure `gd_fts_search` wraps the async request with a bounded wait and
      returns -3 when a dictionary has no full-text index yet.

## 4. Android JNI + IPC

- [x] 4.1 Add `nativeFtsIndex`, `nativeFtsIndexState`, `nativeFtsSearch` to
      `jni_bridge.cc` + `NativeEngine.kt` (mirroring existing group methods).
- [x] 4.2 Add opcodes `OP_FTS_INDEX`, `OP_FTS_INDEX_STATE`, `OP_FTS_SEARCH` to
      `EngineService.kt` + `EngineClient.kt` with the `fts*` Future API
      (`callInt` / `callBytes`) and a `callIntArray`/string parse.
- [x] 4.3 Verify an end-to-end JNI→service→client round-trip builds (Kotlin
      compiles; native lib links). Verified: `assembleDebug` succeeds for
      arm64-v8a + x86_64.

## 5. ViewModel + UI

- [x] 5.1 Add FTS state to `MainViewModel`: `_ftsResults`,
      `_ftsIndexStates` (per-dict index-state map), `_ftsBuilding` flags; add
      `ftsSearch(query, mode)`, `ftsIndex(dictIndex)`, `ftsState(dictIndex)`.
- [x] 5.2 Add a `Dest.FTS` + `FtsScreen` (query field, mode selector, index
      status list, results list) wired into `MainActivity.kt`; results rows tap
      through `viewModel.lookup(headword)`.
- [x] 5.3 Surface the per-dictionary index state ("built / building / missing")
      and trigger index build on demand with an in-progress indication.
- [x] 5.4 Reuse active-group lookup: results run against the active group;
      entry point appears on the search screen.

## 6. Verification (host + device)

- [x] 6.1 Host smoke: extend `smoke/main.cpp` to index the StarDict fixture,
      run `gd_fts_search("smoke")`, assert the headword is returned; update
      `engine-smoke.yml` assertion.
      Verified locally: `gd_fts_search("mdx", plain) -> smoke	Smoke`; a body
      word ("mdx", inside the "smoke" article, not a headword) resolves to the
      article headword. The smoke fixture also needed `sametypesequence=m`
      (plain body entries) so StarDict articles parse at all. Wildcard mode
      additionally requires patch 0003: upstream's `set_max_expansion( 1 )`
      made Xapian throw WildcardError for any prefix matching >1 term (see
      design.md D5), so `read*` silently returned nothing; the patch raises
      the cap to 100 and the smoke pins it with `gd_fts_search("t*")`.
- [ ] 6.2 Build the android APK; install on Motorola ThinkPhone.
- [ ] 6.3 Load a dictionary, run a keyword FTS query that matches a body
      word (e.g. a term inside an article, not a headword); expect the article's
      headword as a result and that tapping it opens the article.
- [ ] 6.4 Verify index state shows built/missing; first search builds the index
      then returns results; rescan rebuilds a stale index.
- [ ] 6.5 Verify prefix matching (`read*` returns the `read`/`reading` hits,
      plain `read` matches exactly), empty-query handling, and that a result
      respects the active group.

## 7. Wrap-up

- [ ] 7.1 Update ROADMAP.md (flip full-text search from planned to in progress,
      then done), and archive the change at completion.