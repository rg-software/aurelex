## Why

GoldenDict-ng is the reference desktop dictionary app, but its Qt Widgets / Qt WebEngine UI cannot run on Android. Users want the goldendict engine (mdict/DSL/StarDict support, wordfinder, article rendering) on their phones. This change launches Aurelex: an Android app that reuses the upstream C++ engine as-is, renders articles in Android's WebView, and stays cheaply upgradable from upstream.

## What Changes

- Introduce a new Android project (Kotlin + Jetpack Compose + WebView) in this repository, targeting a **mobile MVP**: offline lookup of native mdict (MDX/MDD), DSL (+ .dz), and StarDict dictionaries.
- Bring in upstream goldendict-ng as a Git submodule pinned to an upstream release tag, and compile the **engine carve** (dict backends for the three formats, `common/*`, `article_maker`, `config`, `wordfinder`, `language`/`langcoder`) into a shared library via Qt 6 (Core/XML/Concurrent only) cross-compiled for Android with NDK. No Widgets, no WebEngine.
- Expose a thin C API (`gd_*`) from the engine library:
  `gd_init`, `gd_scan_dicts`, `gd_lookup`, `gd_suggest`, `gd_get_resource`, `gd_get_audio`, `gd_cleanup`.
- Implement the UI over JNI: search with wordfinder suggestions, article HTML in WebView, intercept `gdlookup://`, `gdau://`, `bres://` scheme links, audio playback for ogg/mp3/wav.
- **Cut scope for v1** (deliberate, documented, extensible): only the three native formats; no network sources, no full-text search (xapian), no Zim/EPWING/Aard/SLOB/BGL/SDict/GLS/XDXF natively — those are converted on a computer (e.g. pyglossary) before copying to the phone.
- Establish the **merge contract**: engine submodule pinned at a tag + a small `patches/` set as the only deviations + a CI smoke test (building the engine and looking up a known word on each upstream bump).
- Delete the old `TODO.md`; its decisions are superseded by this change's artifacts.

## Capabilities

### New Capabilities

- `dictionary-management`: scanning user-selected dictionary folders, which formats are supported (mdict, DSL, StarDict) and which are out of scope, index build/validation and reindex-on-engine-change on device, enumeration of loaded dictionaries, and single-group ordering.
- `lookup`: headword search with prefix/fuzzy suggestions from `wordfinder`, article HTML rendering via `article_maker` into a WebView, loading embedded resources (MDD images/audio), playing pronunciation audio (ogg/mp3/wav), and handling goldendict's custom URL schemes (`gdlookup://`, `gdau://`, `bres://`).

### Modified Capabilities

- None. No upstream specs exist in this repository yet.

## Impact

- **Upstream interplay**: `engine/` Git submodule of goldendict-ng (pinned tag), `patches/` containing only deviations that cannot be upstreamed; upstream `src/` files are never edited in place.
- **Toolchain**: Android NDK + Qt 6 (Core/XML/Concurrent) for android target; cross-compiled deps `bzip2 zlib liblzma libiconv lzo opencc hunspell fmt tomlplusplus` (xapian, libzim, openssl deferred/cut).
- **Engine carve**: the compiled source subset is our own file list inside the Android build only — upstream files are selected, not modified.
- **New code**: Kotlin app under `app/`, JNI boundary thin layer, C API header.
- **Behavior removed vs desktop**: system tray, scan popup, global hotkeys, network dictionary sources, full-text search, TTS, program actions, the full preferences surface.