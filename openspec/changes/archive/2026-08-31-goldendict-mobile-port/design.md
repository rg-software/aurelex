## Context

goldendict-ng is a monolithic Qt 6 Widgets / Qt WebEngine desktop app: upstream's CMake globs `src/*.cc` into one executable (see proposal.md — Why). There is no pre-existing engine library to extract; the Android port must carve a subset of upstream sources and compile it with a different frontend. Android cannot use Qt Widgets or Qt WebEngine, so rendering moves to the platform WebView. The space between the upstream engine and Android is thin but must be designed so upstream merges stay cheap.

## Goals / Non-Goals

**Goals:**
- Compile the engine carve byte-for-byte from upstream where possible; every deviation is pushed into a thin boundary so merges stay near-zero-effort.
- A C API + JNI boundary that the Kotlin UI can treat as the only "engine contract".
- Reproducible upstream bumps: pin a tag, apply a tiny patch set, CI smoke-test.
- Small, focused v1 that grows case-by-case without speculative architecture.

**Non-Goals:**
- Full desktop feature parity (no network sources, no scan popup, no FTS in v1).
- Rewriting the dictionary formats in Kotlin.
- Maintaining our own reimplementation of Qt string/container/XML/regular-expression types.

## Decisions

### D1. Strategy: verbatim engine + Qt core modules as a linked native lib
Compile the carve with Qt 6 core modules cross-compiled for the Android target and link them into a plain JNI shared library; do NOT shim Qt types onto std::, and do NOT reimplement formats in Kotlin.

Refinement (resolved while reading the carve): **we need Qt-Core, but not the Qt Android app framework.** The carve is QtCore-bound at the DNA level — `QObject`/moc/signals (LoadDictionaries emits signals, ArticleRequest wires queued connections), `QString`, `QDir`/`QFileInfo`, `QThreadPool`, `QFile`/`QUrl`/`QMutex`, `QRegularExpression` — these are load-bearing, not garnish, so Qt is unavoidable. But "Qt on Android" here only means linking the compiled **Core/XML/Concurrent** libraries against a normal Kotlin/Compose app running a JNI `.so`. We do **not** use `QtActivity`, `androiddeployqt`, QML, QtQuick, or Qt WebEngine. The resulting `.so` is just a native dependency inside an ordinary Android app.

Alternatives considered:
- **Homegrown QString/QXmlStreamReader/etc. shim** — rejected. The carve uses QtCore everywhere (QMutex, QFileInfo, QCryptographicHash, QRegularExpression, QXmlStreamReader…). A shim means we own a private fork of part of the Qt API permanently; every upstream use of a Qt API becomes merge tax.
- **Kotlin native format readers** — rejected. MDX/DSL/StarDict are decompiled/reverse-engineered edge-case mines; type-fidelity and merge-friendliness both die.

The real cost is toolchain setup (Qt for Android + cross-compiled deps), which Phase 0 spikes.

### D2. Boundary: C API + JNI, wired through the existing GlobalBroadcaster seam
The engine keeps its own internal seams; the JNI layer exposes the C API
(`gd_init`, `gd_scan_dicts`, `gd_lookup`, `gd_suggest`, `gd_get_resource`, `gd_get_audio`, `gd_cleanup`) and nothing else. Upstream's `GlobalBroadcaster`/config singletons already decouple dict backends from frontend code — the Android frontend plugs into that seam instead of a Qt widget tree.

The only carved source needing handling:
- Icon code in `dict/dictionary.cc` uses QtGui (`QIcon`/`QImage`/`QPainter`). **Resolved by the spike: the carve links `Qt6::Gui`** (article rendering needs `qGuiApp->devicePixelRatio()` via `getOptimalIconSize`), so the icon code compiles as-is and nothing is stubbed there. The earlier "keep carve QtCore-only" goal was superseded by the D1 refinement recorded in Open Questions.

### D3. Merge contract: tag-pinned submodule + small patch set + CI smoke
- `engine/` points at an upstream **release tag** (not rolling master), so index format + code are versioned together and bumps are batched.
- A `patches/` directory holds the only deviations: the icon stubs and any glue that cannot be upstreamed — target: fewer than ~3 small files.
- CI: bump tag → apply patches → build → smoke test (lookup a known word, assert non-empty HTML) → report. A failing smoke stops a bump.

### D4. Rendering: Android WebView + intercepted scheme links + served resources
Articles are HTML produced by upstream `article_maker` with goldendict's custom URLs. The WebViewClient intercepts the schemes and serves the resources the article references, so the HTML stays byte-for-byte upstream:

- `gdlookup://` → in-app lookup (navigate).
- `bres://` → resource bytes from the engine (`gd_get_resource`).
- `gdau://` → audio via engine → on-device player (ogg/mp3/wav).
- `gico://` → dictionary icon (asset or generated), cut-styled per original.
- `qrc:///` → see D9.

### D9. Article-header resource strategy (provisional)
Upstream embeds Qt-compiled-in resources in every article header: `qrc:///scripts/*` (jquery-3.6.0.slim, gd-custom, gd-builtin, mark, iframeResizer…), `qrc:///article-style*.css`, and `qrc:///qtwebchannel/qwebchannel.js` driving `new QWebChannel(qt.webChannelTransport, …)`. Android WebView has no `qrc:///` scheme and no live C++/JS bridge.

Decision (resolved from the resource inventory; provisional until the toolchain spike runs): handle both at the WebView boundary so `article_maker` is untouched:

- **Serve `qrc:///` assets from Android `assets/`** — copy the exact upstream scripts/stylesheets into the app bundle and map URL→asset in `WebViewClient.shouldInterceptRequest`. No rewriting of emitted HTML, so the markup stays upstream-faithful.
- **Ship a no-op `qwebchannel.js` shim** at the `qrc:///qtwebchannel/qwebchannel.js` path. The desktop bridge only carries in-page `articleview` interactions (copy/pronounce/scroll) that our Kotlin UI replaces; article *content* rendering never depended on the live bridge. A shim that defines `QWebChannel`/`qt` harmlessly lets the unchanged header run without a bridge and without JS errors — preferred over stripping the block, because stripping would be an `article_maker` deviation (a patch) whereas a shim is a pure-boundary file.
- A **real** bridge can be mounted later only if a (b)-list feature needs it — none in v1 does.

Rationale: this is the maximal-fidelity option; the only artifact v1 adds is a small, self-contained boundary layer (asset map + shim), keeping `article_maker` and the carved engine byte-for-byte upstream.

### D5. Index cache is engine-versioned → reindex rule
Upstream's index cache files are tied to the engine version. Because all dictionaries live on the device and the engine is tag-pinned, we adopt a contract: when the engine version/index-format changes, existing indexes are invalid and the app rebuilds with user-visible progress (see specs — dictionary-management). No silent cache reuse across engine versions.

### D6. Dependency and build subset
Android cross-compiled deps (via vcpkg android triplet, established by the toolchain spike):
`zlib bzip2 liblzma lzo fmt tomlplusplus`
(installed for `arm64-android` + `x64-android` at `C:\vcpkg\installed\<triplet>`).

**minSdk 28** (Android 9+). Rationale from the spike: Android's bionic provides `iconv` natively
only at API >= 28, and vcpkg's GNU libiconv cannot cross-compile for android (autotools wall, same
as hunspell). Rising to 28 means iconv comes from the platform; falling at 24 would force vendoring
GNU libiconv into the carve. In 2026 Android 9+ is effectively the entire device base.

Cut for v1, confirmed by the spike:
- `libiconv` — unnecessary at minSdk 28 (bionic provides it).
- `opencc` — vcpkg marks it unsupported on android (arm | uwp); only needed by the Chinese transliteration file, which the carve omits (no `MAKE_CHINESE_CONVERSION_SUPPORT`).
- `hunspell` — its autotools build fails to cross-compile for android with NDK r23; only used by `dict/hunspell.cc` morphology ("Close words"). `wordfinder` still provides prefix/fuzzy suggestions without it.
- Dropped as before: `xapian` (FTS), `libzim`, `openssl` (QtNetwork/network sources), EPWING's `eb` submodule, `breakpad`.

Both cut deps are additive later (bindings/ports allowing), so this stays a v1 cut, not a permanent exclusion.

### D7. Cut formats; everything else converts on a computer
v1 loads mdict, DSL, StarDict natively. Other desktop formats (BGL, SDict, XDXF, GLS, Aard, SLOB, LSA, Zim, EPWING) are deliberately cut: users convert to StarDict/MDX on a computer (e.g. pyglossary) and copy over. The cut list is a document, not dead code — formats can be added back by adding one `.cc` to the carve's file list.

### D8. Deferred audio: no speex in v1
Speex (`.spx`) audio is common in older mdict/StarDict packs but Android's players cannot decode it. v1 supports ogg/mp3/wav and treats spx as unsupported-but-non-crashing (see specs — lookup). A future change can add libspeex decoding without disturbing the specs.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| Qt-for-Android + NDK dep cross-compile fails or eats weeks | Phase 0 spike gates everything; fallback path exists (drop hunspell/opencc first, then assess). If needed, revisit D1 toward a minimal shim — but only for the QtCore surface actually used. |
| Upstream refactors the seam/GlobalBroadcaster, breaking our boundary | Boundary is one C API over one seam; patch set is small and re-auditable on each bump. |
| Index format drifts silently between upstream releases | D5's version rule: reindex triggered + surfaced to the user on any engine bump. |
| MDX/DSL/StarDict edge cases differ on phone (encoding, filesystem case) | Security/robustness specs (unsupported format, missing resource, not-found) keep failures graceful; case-by-case fixes via `patches/`. |
| FTS absence disappoints power users | Explicitly a v2 candidate in the (b) cut list; activation is additive (xapian back). |
| `.mdd`/big dictionaries + limited disk | Index storage on app-private storage; SAF selection keeps files readable without broad permission. |

## Cut scope register (desktop features deliberately not in v1)

Living list of desktop features cut for the mobile MVP, kept as a document rather than dead code. Format support per D7 is a separate register (formats served by pyglossary conversion).

**(a) No sense on mobile — cut permanently:**
- System tray / docking integration
- Global hotkeys; scan/hover popup
- Mouse gestures
- External-program integration / "external programs" machinery
- Print / PDF export
- The full desktop preferences surface (kept: a minimal settings screen)

**(b) Make sense on mobile — consider later (additive, case-by-case):**
- Share-sheet / intent lookup ("Look up in GoldenDict")
- Clipboard lookup shortcut
- History / recent-lookups screen
- Favorites (swipe-to-save)
- Text-to-speech pronunciation
- Dark mode for the article view
- Quick-settings tile / home-screen widget
- Multi-group management UI (engine already supports groups; single group in v1 per specs)
- Full-text search (re-enable xapian)
- Pre-built desktop-generated index caches copied along with dictionaries
- Translate-later / word-list export

Each (b) item lands only through the normal flow: does it touch the boundary API (engine change → patch pipeline) or not (pure Kotlin → add anytime)?

## Migration Plan

Greenfield app — no existing users or data to migrate. "Migration" is the Phase 0→1 path:
1. Spike: Qt6-for-Android + deps cross-compile + on-device `gd_lookup` smoke (deletes or confirms D1/D6).
2. If spike passes → build boundary + carve + UI per tasks.
3. If spike stalls → fall back per D1 risk matrix.

## Spike conclusion (task 1.7)

The toolchain spike **passed**; D1/D6 confirmed with refinements. Evidence:

- **Carve compiles for Android**: `libaurelex.so` built for `arm64-v8a` + `x86_64` (Qt 6.6.3 android kits via aqtinstall + vcpkg deps). Also builds as a host Windows smoke tool for CI without a device.
- **End-to-end lookup works**: host smoke (`gd_init` → `gd_scan_dicts` → `gd_suggest` → `gd_lookup`) loaded a synthetic StarDict and returned real upstream HTML (2794 B, including the `qrc:///` + `qwebchannel` header), exit 0.
- **QtGui is required, not just Core**: article rendering calls `getOptimalIconSize()` → `qGuiApp->devicePixelRatio()` (dictionary.cc:258). The carve must instantiate a `QGuiApplication` (not just `QCoreApplication`) and link `Qt6::Gui` — confirmed; the open-question "QtCore-only" is answered: **link QtGui**.
- **minSdk 28 resolved** (see D6): bionic provides iconv at API 28+; vcpkg GNU libiconv can't cross-compile for android.
- **Bug found & fixed in the boundary**: `ArticleMaker` stores `const vector& groups`/`dictionaries` **by reference**; the boundary must keep that storage alive in engine state (a temporary group vector caused a Release-only AV in `makeDefinitionFor`). Recorded so the JNI layer does the same.
- Deps cut confirmed: `opencc` (unsupported on android), `hunspell` (autotools fails to cross-compile), both additive later. FTS stubbed out at the boundary (`fts_stub`, shadowed `ftshelpers.hh`, `ui_fulltextsearch.h` shim) — no xapian needed.

Remaining on-device validation (real device/emulator) is task-gated: the smoke now runs on host; Android APK loads `libaurelex.so` and will be exercised in task 3 (JNI boundary).

## Open Questions

- Exact Qt-version and dep-version pairs for the Android toolchain — resolved by the Phase 0 spike, not by this design.
- Storage-selection UX: SAF document tree vs `MANAGE_EXTERNAL_STORAGE` — **resolved: SAF `OpenDocumentTree`** (no broad storage permission). The engine's `gd_scan_dicts` needs a real path, so the app resolves the tree's physical path (`primary:` → `/storage/emulated/0/...`) and scans in place (critical for large `.mdd`); when the provider is unresolvable it stages copies into app-private storage first (see `SafResolver.kt`, task 4.1).
- Whether desktop-side index generation (pre-built caches copied along with dictionaries) ever becomes worth supporting — a future enhancement, not a blocker; D5 already keeps the index format honest.
- Dark-mode/theming approach for the article WebView — deferred polish, additive.
- Scope of "QtCore-only": **resolved by the spike — link `Qt6::Gui`** (article rendering needs `qGuiApp->devicePixelRatio()` via `getOptimalIconSize`). The carve instantiates a `QGuiApplication` (works headless with the offscreen platform; on Android the host app owns the GUI).