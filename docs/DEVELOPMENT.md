# Development

Everything a contributor (human or AI agent) needs to build, run, and extend
Aurelex. If you are a user, see the top-level `README.md` instead.

## Repo layout

- `engine/` — goldendict-ng submodule, pinned at a release tag, **never edited in place**.
- `patches/` — the only deviations from the pinned source (`.patch` files), applied by `scripts/apply-patches.*`.
- `carve/` — the `gd_*` C boundary (`goldendict.h`, `gd_boundary.cc`) + selected engine
  sources compiled once as an object library, shared by the Qt app and the CI smoke tool.
- `app/` — the Qt app (QML + WebView, Android) that consumes the carve in-process.
- `openspec/` — planning artifacts (proposals, specs, design, tasks); the design is the source
  of truth for scope.
- `docs/` — in-repo guidance. Start here, then follow the link you need:
  - `DEVELOPMENT.md` — this file: layout, build, tests, workflow.
  - `ENGINE.md` — the pinned goldendict-ng source, the four deviation patches, the bump procedure.
  - `TESTING.md` — the on-device verification checklist (what is verified, what is not).
  - `REMOTE-CATALOG.md` — the remote catalog's manifest format, hosting, and free-space rules.
  - `KAIKKI-CONVERSION.md` — building DSL dictionaries from kaikki.org extracts.
  - `SIGNING.md` — signing channels, Play/F-Droid split, app identity.
- `scripts/` — `apply-patches.*`, fixture generators, build helpers, and
  `kaikki-to-dsl.py` (build DSL dictionaries from kaikki.org Wiktionary extracts).

## Working contract (read before changing anything)

The repository rules for agents and contributors live in `AGENTS.md`. Key rules:

- Never edit `engine/` in place. Deviations live in `patches/` or the boundary layer.
- Do not shim Qt types; the carve compiles with real Qt 6.
- The Qt app talks to the engine only through the `gd_*` C boundary.
- Work flows through OpenSpec changes first; implementation does not run ahead of the plan.

## Building the app

The app is a Qt Quick/WebView Android app built from `app/`.
Requirements: JDK 17, Android SDK + NDK r23c, Qt 6.6.3 android + desktop kits, vcpkg deps
(`zlib bzip2 liblzma lzo fmt xapian`), and **PowerShell 7 (`pwsh`)** — the script
uses PS7-only syntax and UTF-8 characters; running it under the legacy
`powershell` 5.1 misdecodes the UTF-8 and fails to parse. On a fresh clone,
populate the engine submodule first (`git submodule update --init`, or clone
with `--recursive`), apply the engine patches, then run the one-shot build
script:

Android TLS needs OpenSSL, which the Qt kit does not ship; the prebuilt libs are
vendored in `app/openssl/<abi>/` and linked into the APK via
`QT_ANDROID_EXTRA_LIBS` (see `app/openssl/README.md`). Those files are tracked in
git, and the CMake configure step **fails** if either one is missing for the ABI
being built — a build cannot silently produce an app with no TLS. If you ever see
*TLS initialization failed* at runtime, the APK is either from a build that
predates that guard or was packaged without the libs; check the APK's
`lib/<abi>/` for `libcrypto_3.so` and `libssl_3.so`.

```powershell
pwsh -File .\app\build.ps1 -Configuration Release            # signed release APK
pwsh -File .\app\build.ps1 -Configuration Release -Bundle    # signed release APK + AAB
```

**Iterative on-device flow.** For local device testing and debugging, use the
Debug build with install, so each edit is built, pushed, and launched in one
step:

```powershell
pwsh -File .\app\build.ps1 -Configuration Debug -Install
pwsh -File .\app\build.ps1 -Configuration Debug -SkipConfigure -Install   # skip cmake reconfigure on repeat runs
```

On a fresh tree the Debug path is self-contained: `build.ps1` packages the Qt
`res/values/libs.xml` (QtLoader resources) and writes a complete `build.gradle`
for non-Release configs, so `assembleDebug` works without extra setup.

`build.ps1` derives its toolchain from `AURELEX_*` env vars (or local defaults); pass `-Install`
to adb-install the result. A signed release APK is produced by the CI workflow
(`.github/workflows/release-qt.yml`) on `vX.Y.Z` tag pushes, using `AURELEX_KEYSTORE_*` secrets;
`versionName`/`versionCode` come from the tag. See `docs/SIGNING.md` for the Google Play /
F-Droid signing split.

## Tests

There are three test layers. None of them needs a device; the device recipe
lives in `docs/TESTING.md`.

### Host unit tests (`app/tests`, desktop Qt)

`app/tests/CMakeLists.txt` is a **standalone host project**, deliberately not part
of `app/CMakeLists.txt` (that one is Android-only and pulls in the whole carved
engine). Each target links only the slice of app code it exercises and stubs
whatever boundary it needs — `article_server_test` links Qt Core + Qt Network and
stubs `gd_get_resource`/`gd_get_audio`; the other four are Qt Core only against
header-only code — so these build and run in seconds on a desktop Qt.

```powershell
cmake -S app/tests -B build-app-tests -DCMAKE_PREFIX_PATH=C:/Qt/6.6.3/msvc2019_64 -G Ninja
cmake --build build-app-tests --config Release
foreach ($t in @('article_server_test','index_migration_test','index_cleanup_test','dictionary_index_test','catalog_test')) {
  & "build-app-tests/$t.exe"; if ($LASTEXITCODE -ne 0) { throw "$t failed" }
}
```

| Target | Covers |
| --- | --- |
| `article_server_test` | `ArticleServer` resource/audio requests, with `gd_get_resource`/`gd_get_audio` stubbed |
| `index_migration_test` | the index-directory path separator and the stray-sweep migration |
| `index_cleanup_test` | index removal on dictionary delete |
| `dictionary_index_test` | display-order ↔ engine-index mapping |
| `catalog_test` | the remote-catalog manifest parser, installed-detection and the free-space preflight constants, against the fixtures in `app/tests/fixtures/` |

Building a single target is often enough while iterating:
`cmake --build build-app-tests --target catalog_test`. Adding a new test means
adding a target here; keep it host-only (the project hard-fails on `ANDROID`).

### Converter tests (`scripts/tests`, Python)

The kaikki converter has its own suite, standard library only, no network — every
audio path either passes `--no-audio-download`, injects a stub downloader, or
blocks the opener:

```powershell
python -m unittest discover -s scripts/tests
```

### Engine smoke test (`carve/smoke`, CI)

`carve/` builds a host smoke tool (`AURELEX_BUILD_SMOKE=ON`) exercised by
`.github/workflows/engine-smoke.yml` on every engine/patch/carve change: it scans a
fixture folder (including a nested-subfolder fixture, asserting recursion), looks
up a known word, and checks FTS + group/remove behavior. **Any engine release bump must
keep the smoke green** — it is the gate that catches an engine merge that
compiles but breaks the boundary.

## On-device verification

`docs/TESTING.md` holds the manual recipes (build/install, lookup, article
rendering, audio, groups, FTS, history/favorites, storage, the remote catalog,
external entry points) with a per-item status. It is the record of what has
actually been seen on hardware, as opposed to what the tests above prove.

## The engine source

Aurelex is not a fork of goldendict-ng; we consume it verbatim from a Git submodule pinned to a
release tag. Only a small patch set deviates, and the CI smoke verifies each release bump. See
`docs/ENGINE.md` for the pin, the bump procedure, and the patch set.

## OpenSpec workflow

Planning artifacts live in `openspec/`. Features and fixes flow through changes:

1. `openspec new change <name>`
2. Draft proposal → design → specs → tasks (default `spec-driven` schema).
3. Implement via the OpenSpec apply workflow.
4. Verify on-device, then archive.

The **archive is the record of what shipped** — `openspec/changes/archive/` holds every completed
change with its tasks and verification notes. Read it before assuming something is unbuilt. There is
no separate roadmap file; the candidate milestones are in the backlog below.

## Backlog (candidate milestones)

Not scheduled, not proposed, not promised. Each one is picked up by opening an OpenSpec change.

- **Translate-later / word-list export** — extract headwords/definitions to a file or anki.
- **Pre-built desktop-generated index caches** — copy indexes alongside dictionaries so the phone
  skips indexing. Boundary work (cache format).
- **Widget fills search with clipboard** — the widget is currently a styled shortcut (RemoteViews
  cannot capture typed text). Tapping it could copy the clipboard into the in-app search field,
  reusing the tile's clipboard-read path. Needs an on-device check that the read happens in the
  foreground activity (Android 10+), same as the tile.
- **Tappable group label on history/favorites rows** — the rows already show a group-name line;
  making it jump to that group and re-run the search is the follow-up.
- **Close the open archived tasks** — `docs/TESTING.md` lists the unverified items, and several
  archived changes still carry unchecked verification tasks. Not new features; this is the gap
  between "shipped" and "known to work".
- **Translation dictionary** — the kaikki converter builds monolingual dictionaries only; a real
  translation dictionary needs sense alignment and word/phrase equivalents that Wiktionary lacks.
  Candidate sources and their coverage/licenses (WordNet / Open Multilingual WordNet, Tatoeba,
  BabelNet) are recorded in `docs/KAIKKI-CONVERSION.md` under "Future: a translation dictionary".

### Dictionary format coverage

Context and effort estimates for these were worked out while fixing StarDict
(`openspec/changes/fix-stardict-staging`). The short version: **pyglossary is the
converter for almost everything** — it reads BGL, EPWING, SLOB, MDict, XDXF,
AppleDict, Lingoes and more, and StarDict is its one writable target — so a native
reader is usually redundant once StarDict import works. Only a format users cannot
reasonably convert is worth engine work.

- **EPWING (native)** — the strongest candidate on *value*, and the reason is not
  convenience: it is *the* format serious Japanese dictionaries ship in, and the
  app already ships a Japanese UI, so a JA-localised app that cannot load a JA
  dictionary is a mismatch. But it is **not** cheap, and it is weaker than it
  first looks on build cost:
  - It depends on the **`eb` (libeb) library** (`engine/src/dict/epwing_book.hh`
    includes `<eb/eb.h>`), which the original design **dropped** — EPWING's `eb`
    submodule is listed among the cut dependencies in the archived
    `goldendict-mobile-port` design (§ D6), because getting it to cross-compile for
    Android was a known wall. So this is a cross-compile project first and a wiring
    project second, unlike BGL/GLS.
  - It is a **directory** format keyed on a `CATALOGS` file, which does not fit the
    boundary's one-primary-file-at-a-time loader (`loadPrimary` in `gd_boundary.cc`
    deliberately isolates each file for crash safety) — that loader needs real
    work, as it does for Dictd.
  - Expect variant risk (JIS X 0208 charsets, several compression schemes;
    `epwing_charmap.cc` covers the charmap side) and no cheap test fixture — there
    is no EPWING equivalent of `make-smoke-stardict.py`, since real EPWING sets are
    CD-ROM-derived.
  Deliberately deferred from the first release. If pursued, scope the variant
  matrix explicitly, treat the `eb` cross-compile as its own spike, and give it a
  release of its own rather than riding along.
- **XDXF (native)** — nearly free: `xdxf.cc` and `xdxf2html.cc` are **already
  compiled into the carve** and simply not wired into the scan filter or dispatch.
  Low value on its own (XDXF is an interchange format, not one people distribute
  dictionaries in, and pyglossary covers it), so do it only as a warm-up or if the
  wiring is being touched anyway.
- **Babylon `.bgl`, GLS `.gls`** — no new dependencies (zlib is already linked).
  Mechanical to add, but pyglossary already converts them, so the argument for
  native support is weak.
- **Aard2 `.slob`, SDict `.dct`, Dictd, LSA `.lsa`** — same reasoning; LSA would add
  libvorbisfile, Dictd is another multi-file format with the `loadPrimary` problem.
  Aard2 and SLOB matter slightly more than the rest because they are the native
  formats of Android dictionary apps, so users may already have them on the phone.
- **Zim `.zim` / Hunspell** — probably not, on purpose. Zim is an offline HTML
  archive rather than a headword dictionary (a different product category, and it
  needs libzim); Hunspell is spellchecking/morphology, not definitions. Hunspell
  was cut in the original design for a *build* reason rather than a product one
  (its autotools cross-compile fails on Android NDK r23; see that design's § D6),
  so it is only worth revisiting if the toolchain problem disappears or someone
  actually wants "close words" morphology.
- **Wiring cost, if a reader is ever added** — the format knowledge is currently
  spread across **three** places, not one:
  1. the scan filter and the per-file dispatch in `carve/gd_boundary.cc`
     (`filters` near the top of `gd_scan_dicts`, and the `else if` chain below it);
  2. the importer's staging filter in Java (`AurelexActivity.isSupportedDictionaryName`
     / `isStardictCompanionName`), which decides what is copied in the first place;
  3. `kDictionaryExtensions` in `app/RemoteCatalog.cpp`, which drives catalog
     install validation and installed-detection.

  Adding a format means touching all three, plus compiling the reader into
  `carve/CMakeLists.txt`. The Java/C++ pair is the recurring trap and the one that
  caused the StarDict bug, because only the boundary was exercised by the smoke
  test. Consider unifying that pair before adding a fourth copy of the knowledge —
  `catalog_test` already covers the C++ side and could cover a shared source.
- **Conversion guidance lives in the README** — the user-facing "convert it
  yourself" path is documented there, and it should stay in sync with this list.

Engine-touching items (pre-built index caches, any native format reader) go through the patch
pipeline (`patches/` + CI smoke); pure-QML items (word-list export, widget clipboard) do not.

## Localization

The app defaults its display language to the system UI language and ships
**English (untranslated base) + Russian + Japanese**. All product copy lives in
Qt translation catalogs; Android surfaces (app label, widgets, tiles,
notifications) use `res/values*/strings.xml`.

**How it works**

- QML strings use `qsTr("…")` with `%1`-style placeholders
  (`qsTr("Indexing (%1 of %2): %3").arg(a, b, c)`); imperative JS strings that
  build WebView HTML (history/favorites chrome) are `qsTr` + `_escHtml`-escaped.
  `Accessible.name` values are deliberately **not** translated — they are the
  stable test IDs documented in `AGENTS.md`.
- C++ user-visible strings use `tr()` (e.g. `EngineController::groupName`'s
  "All" fallback). Diagnostic/protocol strings (`gd_* failed (rc=%1)`, HTTP
  status bodies in `ArticleServer`) stay English behind the localized "engine
  error:" banner.
- `main.cpp` installs a `QTranslator` at startup from
  `QLocale().uiLanguages()` (the Qt Android kit does not compile
  `QGuiApplication::uiLanguages()`): for each UI language it tries the full
  locale first (`aurelex_ru_RU.qm`) then the language-only code
  (`aurelex_ru.qm`) from the embedded `:/i18n/` resource, and falls back to
  English (with a `qInfo` line) without aborting.

**Source strings are the catalog keys** — this matters when editing English.

Unlike Android `strings.xml` (where the resource `name` is a language-independent
key and only the value changes per locale), a Qt catalog entry is keyed by the
literal English `qsTr`/`tr` argument it was extracted from (`<source>`). Two
consequences:

- **Never edit `<source>` inside a `.ts`.** Its only true home is the QML/C++
  code; `lupdate` regenerates it and (`-no-obsolete`) deletes any message whose
  source no longer appears in the sources — a hand-edited key just vanishes on
  the next extract.
- **Changing English copy means retranslating in every catalog.** Edit the
  string in the source and re-extract: the old message is dropped as obsolete
  and a fresh `<message>` appears with an *empty* `<translation>`. Fill it in
  each shipped catalog — no translation carries over, because the key changed.

**Adding or updating text**

1. Write or edit the user-facing string with `qsTr`/`tr` in the QML/C++
   source. If only the target-language text changes (English stays correct),
   skip to step 3 and edit translations directly.
2. Extract and compile catalogs:
   `pwsh -File .\scripts\update-translations.ps1 -Languages @("ru","ja")`
   (`-NoCompile` to refresh the `.ts` only). `lupdate` updates the `.ts` to
   match the sources; `lrelease` then recompiles the `.qm`. Requires Qt's
   `lupdate`/`lrelease` (`AURELEX_QT_BASE`/`AURELEX_QT_HOST` default to
   `C:\Qt\6.6.3` / `msvc2019_64`).
3. Translate: fill the `<translation>` of any new (or freshly emptied)
   `<message>` directly in `app/i18n/aurelex.ru.ts` / `aurelex.ja.ts`, then
   re-run the script to recompile the `.qm`. Translation-only tweaks do not
   need step 2.
4. **Commit the compiled `.qm` files** — they are the shipped artifacts; both
   are embedded via the `qt_add_resources(aurelex "i18n" ...)` block in
   `app/CMakeLists.txt`.
5. If a new system language is added, also extend `app/android/res/values-xx/`
   (app label, tile/widget labels, notification strings) and add it to the
   `-Languages` array.

Android notification/launcher strings resolve via `getString(R.string.*)` in
`StagingService`/`IndexingService`; the indexing-progress template is a c-format
`formatted="false"` resource formatted at runtime (`%1$d of %2$d: %3$s`).