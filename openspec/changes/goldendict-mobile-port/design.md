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

### D1. Strategy: verbatim engine + Qt 6 (Core/XML/Concurrent) for Android
Compile the carve with Qt 6 core modules officially built for the Android target; do NOT shim Qt types onto std::, and do NOT reimplement formats in Kotlin.

Alternatives considered:
- **Homegrown QString/QXmlStreamReader/etc. shim** — rejected. The carve uses QtCore everywhere (QMutex, QFileInfo, QCryptographicHash, QRegularExpression, QXmlStreamReader…). A shim means we own a private fork of part of the Qt API permanently; every upstream use of a Qt API becomes merge tax.
- **Kotlin native format readers** — rejected. MDX/DSL/StarDict are decompiled/reverse-engineered edge-case mines; type-fidelity and merge-friendliness both die.

The real cost is toolchain setup (Qt for Android + cross-compiled deps), which Phase 0 spikes.

### D2. Boundary: C API + JNI, wired through the existing GlobalBroadcaster seam
The engine keeps its own internal seams; the JNI layer exposes the C API
(`gd_init`, `gd_scan_dicts`, `gd_lookup`, `gd_suggest`, `gd_get_resource`, `gd_get_audio`, `gd_cleanup`) and nothing else. Upstream's `GlobalBroadcaster`/config singletons already decouple dict backends from frontend code — the Android frontend plugs into that seam instead of a Qt widget tree.

The only carved source needing handling:
- Icon code in `dict/dictionary.cc` uses QtGui (`QIcon`/`QImage`/`QPainter`). Stub those few icon methods under the boundary so the carve stays QtCore-only (tree differs from upstream by a handful of lines, kept in `patches/`).

### D3. Merge contract: tag-pinned submodule + small patch set + CI smoke
- `engine/` points at an upstream **release tag** (not rolling master), so index format + code are versioned together and bumps are batched.
- A `patches/` directory holds the only deviations: the icon stubs and any glue that cannot be upstreamed — target: fewer than ~3 small files.
- CI: bump tag → apply patches → build → smoke test (lookup a known word, assert non-empty HTML) → report. A failing smoke stops a bump.

### D4. Rendering: Android WebView + intercepted scheme links
Articles are HTML produced by upstream `article_maker` with goldendict's custom URLs. The WebView intercepts `gdlookup://` (in-app lookup), `bres://` (resource from engine), `gdau://` (audio via engine → on-device player). This mirrors how upstream's own web interceptor works, so HTML stays upstream-faithful.

### D5. Index cache is engine-versioned → reindex rule
Upstream's index cache files are tied to the engine version. Because all dictionaries live on the device and the engine is tag-pinned, we adopt a contract: when the engine version/index-format changes, existing indexes are invalid and the app rebuilds with user-visible progress (see specs — dictionary-management). No silent cache reuse across engine versions.

### D6. Dependency and build subset
Android cross-compile list, cut down from vcpkg.json:
`bzip2 zlib liblzma libiconv lzo opencc hunspell fmt tomlplusplus`
(+- whatever the toolchain spike proves necessary).
Dropped for v1: `xapian` (FTS), `libzim` (Zim), `openssl` (QtNetwork/network sources), EPWING's `eb` submodule, `breakpad`.

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

## Open Questions

- Exact Qt-version and dep-version pairs for the Android toolchain — resolved by the Phase 0 spike, not by this design.
- Storage-selection UX: SAF document tree vs `MANAGE_EXTERNAL_STORAGE` — an implementation choice under the "select a folder" requirement; decide at task time.
- Whether desktop-side index generation (pre-built caches copied along with dictionaries) ever becomes worth supporting — a future enhancement, not a blocker; D5 already keeps the index format honest.
- Dark-mode/theming approach for the article WebView — deferred polish, additive.