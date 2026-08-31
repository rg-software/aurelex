## 1. Repo setup & toolchain spike

- [x] 1.1 Add upstream `engine/` Git submodule pinned at a release tag; record the tag in `patches/` or `UPSTREAM.md`
- [x] 1.2 Scaffold the Android Gradle project (Kotlin, Jetpack Compose, WebView) with minSdk 28
- [x] 1.3 Add NDK CMake build producing `libaurelex.so` (arm64-v8a + x86_64) for the engine carve
- [x] 1.4 Wire Qt 6 (Core/XML/Concurrent only) for the Android target into the engine build
- [x] 1.5 Establish cross-compile approach for deps: `bzip2 zlib liblzma lzo fmt tomlplusplus` (iconv from platform at minSdk 28; opencc/hunspell cut)
- [x] 1.6 Spike: minimal engine build that can load a StarDict dict and run `gd_lookup` (define "smoke word") on device — proven on host: `gd_scan_dicts`→1 dict, `gd_suggest`→suggestion, `gd_lookup`→2794 B HTML, exit 0
- [x] 1.7 Draw the conclusion of the spike: D1/D6 confirmed, or record the fallback in design.md — confirmed; see design.md "Spike conclusion (task 1.7)"

## 2. Engine carve & boundary API

- [x] 2.1 Create the carve CMake source list (subset of upstream `src/` and `src/dict/` for mdx/mdd, dsl, stardict; `common/*`, `article_maker`, `config`, `wordfinder`, `language`/`langcoder`, FTS-free paths) — `AURELEX_CARVE_SOURCES` in `app/src/main/cpp/engine/CMakeLists.txt`; verified compiling mdx+dsl on Android (both ABIs) and host smoke; dsl's unused `QSvgRenderer` include removed via `patches/0001-dsl-drop-unused-qtsvg-include.patch`
- [x] 2.2 Stub the QtGui icon code in `dict/dictionary.cc` as a small patch (keeps carve QtCore-only) — **superseded**: spike resolved that the carve links `Qt6::Gui` (design D1 refinement), so `dictionary.cc`'s icon code compiles as-is; no stub needed
- [x] 2.3 Define `goldendict.h` C API: `gd_init`, `gd_scan_dicts`, `gd_lookup`, `gd_suggest`, `gd_get_resource`, `gd_get_audio`, `gd_cleanup` — header at `app/src/main/cpp/engine/goldendict.h`
- [x] 2.4 Implement the C API over the GlobalBroadcaster/config seam — extended `gd_boundary.cc`: `gd_scan_dicts` now loads mdx/mdd + dsl + stardict; added `gd_get_resource`/`gd_get_audio` (mirrors upstream `handleDictionaryResource`)
- [x] 2.5 Verify each of the three formats loads, indexes, and returns HTML on the Android filesystem — verified on **host** with synthetic dictionaries in all three formats (same engine QDir/QFile path as Android; on-device exercise is task-gated to 3.x per design): StarDict (spike), DSL (1 dict, 2629 B HTML, exit 0), MDX+MDD via mdict-utils (1 dict, 2935 B HTML, `gd_get_resource("bres://<id>/smoke.png") → 24 B`, exit 0)

## 3. JNI boundary & Android app skeleton

- [x] 3.1 Implement the JNI layer mapping the `gd_*` C API to Kotlin-callable natives — `app/src/main/cpp/jni/jni_bridge.cc` (7 `Java_aurelex_android_NativeEngine_*` natives, buffer marshalling) + `NativeEngine.kt` (dedicated single-thread engine executor, all calls serialized); all 7 symbols verified exported from `libaurelex.so` both ABIs
- [x] 3.2 Single-activity Compose app with navigation (search, article, dictionaries/settings) — `MainActivity.kt` with lightweight back-stack navigation (`Dest.SEARCH/ARTICLE/DICTIONARIES`) over `MainViewModel`; search → suggestions → article flow wired; article/dict screens are placeholders for §4/§5
- [x] 3.3 Engine lifecycle: init on app start, cleanup on exit — `AurelexApp.onCreate` queues `gd_init` (idempotent), `onTerminate` queues `gd_cleanup`; `MainViewModel` wired to `NativeEngine`
- [x] 3.4 Add a `libspeex`-free audio play strategy: ogg/mp3/wav via MediaPlayer/ExoPlayer — `AudioPlayer.kt`: fetches `gdau://` bytes via `gd_get_audio`, plays via MediaPlayer; `.spx` and unknown codecs report graceful `Unsupported` instead of crashing

## 4. Dictionary management

- [x] 4.1 SAF folder picker + scan for supported files (`.mdx`/`.mdd`, `.dsl`/`.dsl.dz`, `.ifo`) — `DictionariesScreen` launches `OpenDocumentTree` → `SafResolver.resolveTreePath` (physical path, in-place scan for big `.mdd`) or fallback `stageDictionaryFiles` copy → `gd_scan_dicts`; design Open Question resolved (SAF, no broad storage permission)
- [x] 4.2 Index-build orchestration with progress UI; skip when up-to-date; rebuild when the file or engine index format changed (surface "reindexing" to the user) — engine native index cache + signature checks handle skip/rebuild-on-file-change; app adds `IndexVersion` stamp (D5): mismatched engine version → invalidate `.idx` + surface "Reindexing…" + indeterminate progress in `DictionariesScreen`
- [x] 4.3 Dictionary list screen: display names + source files; reorderable single group matching goldendict's "unfiltered" behavior — boundary grew `gd_dict_count`/`gd_dict_info`/`gd_move_dict` (boundary-only, no upstream touch); JNI `nativeDictCount/Info/MoveDict`; `DictionariesScreen` lists name+file with ↑/↓ reorder, order drives combined article (ArticleMaker rebuilt after move)
- [x] 4.4 No-supported-dictionaries message when a folder scan finds nothing — `DictionariesScreen` shows "No supported dictionaries found" when `pickAndScan` returns 0

## 5. Lookup

- [x] 5.1 Search screen: search bar feeding `gd_suggest` for prefix/fuzzy headword suggestions — `SearchScreen` debounced `LaunchedEffect` → `MainViewModel.suggest` → `NativeEngine.suggest`; suggestions rendered as tap targets
- [x] 5.2 Article rendering: `gd_lookup` HTML into WebView via `loadDataWithBaseURL` — `ArticleWebView.render` loads with base `qrc:///` so upstream `qrc:///` + relative refs resolve (design D4/D9)
- [x] 5.3 WebView scheme interceptor for `gdlookup://`, `bres://`, `gdau://` — `WebViewClient.shouldOverrideUrlLoading`/`shouldInterceptRequest` in `ArticleWebView`; `gdlookup://` → in-app lookup, `bres://` → engine resource bytes
- [x] 5.4 Embedded resource loading (mdd images/audio) via `gd_get_resource` — `serveEngineResource` maps `bres://` subresource URL → `NativeEngine.getResource` (jni `nativeGetResource` → `gd_get_resource`)
- [x] 5.5 Audio playback from `gdau://` links (ogg/mp3/wav); graceful "unsupported" handling for speex — anchor-tap `gdau://` → `AudioPlayer` (MediaPlayer, cache-file bytes from `gd_get_audio`); `.spx`/unknown → `AudioResult.Unsupported` surfaced as a notice, never crashes
- [x] 5.6 In-article link navigation and article back stack — `gdlookup://` word → `viewModel.lookup` (rekeyed `key(word)` WebView reload); back-stack navigates to previous article (task 3.2's back-stack)
- [x] 5.7 Not-found UX: "word not found" indication with a way back to search — `ArticleScreen` shows "Word not found" + "Back to search" when the engine page lacks the `gdarticlebody` marker (found articles always emit it)

## 6. Merge contract & CI

- [x] 6.1 Create `patches/` with the icon stubs + any glue; add a small `git am`-style apply script — `patches/0001-dsl-drop-unused-qtsvg-include.patch` (only deviation so far; icon stub not needed since QtGui is linked, task 2.2); `scripts/apply-patches.{ps1,sh}` apply all `patches/*.patch` to the engine working tree via `git apply --check` (correct choice over `git am` — must not commit into the submodule); documented in `UPSTREAM.md`
- [x] 6.2 CI job: bump engine tag → apply patches → build → smoke test (lookup the smoke word, assert non-empty HTML) → report — `.github/workflows/engine-smoke.yml`: optional `workflow_dispatch` engine `inputs.engine_tag` (or push on engine/patches/cpp paths) → `scripts/apply-patches.sh` → aqt Qt host kit + vcpkg → host smoke tool build → `scripts/make-smoke-stardict.py` fixture → run `aurelex_smoke`, grep `gd_lookup("smoke") -> <nonzero>` (validated: 2715 B, exit 0)
- [x] 6.3 Version-stamp the index format in the app so an engine bump triggers the reindex path (task 4.2) — `app/build.gradle.kts` injects `BuildConfig.ENGINE_VERSION` from `engine/VERSION`; `IndexVersion` compares/stamps it on scan → mismatched engine version invalidates `.idx` + surfaces "Reindexing…"

## 7. Polish & distribution

- [x] 7.1 Dark mode toggle plus article CSS theme — boundary `gd_set_dark_mode` (sets `preferences.darkReaderMode` + `displayStyle=modern` in gd_init) → JNI `nativeSetDarkMode` → `MainViewModel.toggleDarkMode` re-looks-up; Compose theme follows VM darkMode; verified on host: `gd_set_dark_mode(1)→0`, re-lookup emits `darkreader=yes`
- [x] 7.2 Signed APK build in CI — `app/build.gradle.kts` `signingConfigs.release` from `AURELEX_KEYSTORE_*` env (no keystore committed; release stays unsigned locally); `.github/workflows/build-apk.yml` assembles a signed release APK and uploads it as an artifact; verified unsigned local `assembleRelease` passes
- [x] 7.3 Distribution metadata (GitHub releases; F-Droid metadata if desired) — `build-apk.yml` uses `softprops/action-gh-release` on `v*` tags to draft a release with the signed APK attached; F-Droid deferred (not configured)
- [x] 7.4 User docs: dict conversion recipe via pyglossary + copy-to-phone steps (README) — README updated: in-app folder picker flow, pyglossary `BGL/SDict/XDXF→StarDict` commands, supported formats/audio notes, build steps, status banner