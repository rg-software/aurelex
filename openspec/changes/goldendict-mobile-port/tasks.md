## 1. Repo setup & toolchain spike

- [ ] 1.1 Add upstream `engine/` Git submodule pinned at a release tag; record the tag in `patches/` or `UPSTREAM.md`
- [ ] 1.2 Scaffold the Android Gradle project (Kotlin, Jetpack Compose, WebView) with minSdk 24
- [ ] 1.3 Add NDK CMake build producing `libaurelex.so` (arm64-v8a + x86_64) for the engine carve
- [ ] 1.4 Wire Qt 6 (Core/XML/Concurrent only) for the Android target into the engine build
- [ ] 1.5 Establish cross-compile approach for deps: `bzip2 zlib liblzma libiconv lzo opencc hunspell fmt tomlplusplus`
- [ ] 1.6 Spike: minimal engine build that can load a StarDict dict and run `gd_lookup` (define "smoke word") on device
- [ ] 1.7 Draw the conclusion of the spike: D1/D6 confirmed, or record the fallback in design.md

## 2. Engine carve & boundary API

- [ ] 2.1 Create the carve CMake source list (subset of upstream `src/` and `src/dict/` for mdx/mdd, dsl, stardict; `common/*`, `article_maker`, `config`, `wordfinder`, `language`/`langcoder`, FTS-free paths)
- [ ] 2.2 Stub the QtGui icon code in `dict/dictionary.cc` as a small patch (keeps carve QtCore-only)
- [ ] 2.3 Define `goldendict.h` C API: `gd_init`, `gd_scan_dicts`, `gd_lookup`, `gd_suggest`, `gd_get_resource`, `gd_get_audio`, `gd_cleanup`
- [ ] 2.4 Implement the C API over the GlobalBroadcaster/config seam
- [ ] 2.5 Verify each of the three formats loads, indexes, and returns HTML on the Android filesystem

## 3. JNI boundary & Android app skeleton

- [ ] 3.1 Implement the JNI layer mapping the `gd_*` C API to Kotlin-callable natives
- [ ] 3.2 Single-activity Compose app with navigation (search, article, dictionaries/settings)
- [ ] 3.3 Engine lifecycle: init on app start, cleanup on exit
- [ ] 3.4 Add a `libspeex`-free audio play strategy: ogg/mp3/wav via MediaPlayer/ExoPlayer

## 4. Dictionary management

- [ ] 4.1 SAF folder picker + scan for supported files (`.mdx`/`.mdd`, `.dsl`/`.dsl.dz`, `.ifo`)
- [ ] 4.2 Index-build orchestration with progress UI; skip when up-to-date; rebuild when the file or engine index format changed (surface "reindexing" to the user)
- [ ] 4.3 Dictionary list screen: display names + source files; reorderable single group matching goldendict's "unfiltered" behavior
- [ ] 4.4 No-supported-dictionaries message when a folder scan finds nothing

## 5. Lookup

- [ ] 5.1 Search screen: search bar feeding `gd_suggest` for prefix/fuzzy headword suggestions
- [ ] 5.2 Article rendering: `gd_lookup` HTML into WebView via `loadDataWithBaseURL`
- [ ] 5.3 WebView scheme interceptor for `gdlookup://`, `bres://`, `gdau://`
- [ ] 5.4 Embedded resource loading (mdd images/audio) via `gd_get_resource`
- [ ] 5.5 Audio playback from `gdau://` links (ogg/mp3/wav); graceful "unsupported" handling for speex
- [ ] 5.6 In-article link navigation and article back stack
- [ ] 5.7 Not-found UX: "word not found" indication with a way back to search

## 6. Merge contract & CI

- [ ] 6.1 Create `patches/` with the icon stubs + any glue; add a small `git am`-style apply script
- [ ] 6.2 CI job: bump engine tag → apply patches → build → smoke test (lookup the smoke word, assert non-empty HTML) → report
- [ ] 6.3 Version-stamp the index format in the app so an engine bump triggers the reindex path (task 4.2)

## 7. Polish & distribution

- [ ] 7.1 Dark mode toggle plus article CSS theme
- [ ] 7.2 Signed APK build in CI
- [ ] 7.3 Distribution metadata (GitHub releases; F-Droid metadata if desired)
- [ ] 7.4 User docs: dict conversion recipe via pyglossary + copy-to-phone steps (README)