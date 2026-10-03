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
  - `REMOTE-CATALOG.md` - the remote catalog's manifest format, hosting, generator workflow, and free-space rules.
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
stubs `gd_get_resource`/`gd_get_audio`; the rest link Qt Core only (header-only
code, plus `RemoteCatalog.cpp` for `catalog_test`) — so these build and run in
seconds on a desktop Qt.

```powershell
cmake -S app/tests -B build-app-tests -DCMAKE_PREFIX_PATH=C:/Qt/6.6.3/msvc2019_64 -G Ninja
cmake --build build-app-tests --config Release
foreach ($t in @('article_server_test','index_migration_test','index_cleanup_test','dictionary_index_test','staged_cleanup_test','staging_rules_test','catalog_test')) {
  & "build-app-tests/$t.exe"; if ($LASTEXITCODE -ne 0) { throw "$t failed" }
}
```

| Target | Covers |
| --- | --- |
| `article_server_test` | `ArticleServer` resource/audio requests, with `gd_get_resource`/`gd_get_audio` stubbed |
| `index_migration_test` | the index-directory path separator and the stray-sweep migration |
| `index_cleanup_test` | index removal on dictionary delete |
| `dictionary_index_test` | display-order ↔ engine-index mapping |
| `staged_cleanup_test` | the containment/sharing guards on deleting a staged import directory |
| `staging_rules_test` | the staging resource rules mirrored by the Java importer: DSL `.files`; StarDict `res` only beside a `.ifo`; an MDX set's loose assets (`.css`/images/fonts) only beside a `.mdx`, and only the bounded set an article embeds |
| `catalog_test` | the remote-catalog manifest parser, installed-detection and the free-space preflight constants, against the fixtures in `app/tests/fixtures/` |

Building a single target is often enough while iterating:
`cmake --build build-app-tests --target catalog_test`. Adding a new test means
adding a target here; keep it host-only (the project hard-fails on `ANDROID`).

### Script tests (`scripts/tests`, Python)

Standard library only, no network needed — the catalog suite reads JSON from
files, and the kaikki converter suite either passes `--no-audio-download`,
injects a stub downloader, or blocks the opener:

```powershell
python -m unittest discover -s scripts/tests
```

This runs both the kaikki converter suite and the catalog tool suite
(`test_build_catalog.py`, covering `scripts/build-catalog.py`).

### Engine smoke test (`carve/smoke`, CI)

`carve/` builds a host smoke tool (`AURELEX_BUILD_SMOKE=ON`) exercised by
`.github/workflows/engine-smoke.yml` on every engine/patch/carve change: it scans a
fixture folder (including a nested-subfolder fixture, asserting recursion), looks
up a known word, and checks FTS + group/remove behavior. **Any engine release bump must
keep the smoke green** — it is the gate that catches an engine merge that
compiles but breaks the boundary.

#### Run it locally against both layouts

The tool asserts across several fixtures, and CI runs it against **two** folders.
A local run against only one of them is how the tool came to be green locally and
red in CI, so run both:

```powershell
# build once
cmake --build build-smoke --config Release --target aurelex_smoke

# 1. combined folder (StarDict + .dsl.dz + nested .dsl) — no block skips
python scripts/make-smoke-stardict.py          $env:TEMP\dic
python scripts/make-example-dicts.py           $env:TEMP\dsl
copy $env:TEMP\dsl\aurelex-basic.dsl.dz        $env:TEMP\dic\
xcopy /E /I $env:TEMP\dsl\aurelex-basic.dsl.files $env:TEMP\dic\aurelex-basic.dsl.files
mkdir $env:TEMP\dic\nested
copy $env:TEMP\dsl\aurelex-lingvo.dsl          $env:TEMP\dic\nested\
.\build-smoke\Release\aurelex_smoke.exe $env:TEMP\cfg $env:TEMP\dic smoke

# 2. MDX-only folder — the format-specific blocks must report =SKIP
python scripts/make-smoke-mdx.py               $env:TEMP\mdx
.\build-smoke\Release\aurelex_smoke.exe $env:TEMP\cfg-mdx $env:TEMP\mdx smoke
```

Both must exit **0**. Each run prints `FIXTURES: …` naming what it found, and a
block whose fixture is absent prints `=SKIP` instead of `=FAIL`.

**A `=SKIP` is not a pass.** CI asserts the *expected* skips per invocation, so a
fixture that silently stops being generated fails the run that expects it rather
than skipping everywhere and passing vacuously. If you add a fixture layout, add
its expected skips too.

**CI runs bash with `-e`.** Never capture a command's exit code as
`out=$(cmd)` followed by `ex=$?`: the substitution aborts the step first, taking
the exit code *and* the output with it, and the run reports a bare exit 1 with no
reason. Use `if out=$(cmd 2>&1); then ex=0; else ex=$?; fi`.

## On-device verification

`docs/TESTING.md` holds the manual recipes (build/install, lookup, article
rendering, audio, groups, FTS, history/favorites, storage, the remote catalog,
external entry points) with a per-item status. It is the record of what has
actually been seen on hardware, as opposed to what the tests above prove.

**Resetting first-run state (the onboarding overlay).** The overlay shows while
`onboarded` is false (`main.qml`: `visible: !engine.onboarded`). The flag is
persisted in the app's private `files/settings.json`, reachable over adb via
`run-as` (debug builds). Write the JSON to a host file and push it — quoting it
inline through PowerShell → `adb shell` → `sh -c` mangles the quotes and fails
with `sh: no closing quote`:

```powershell
$adb = "C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe"
$pkg = "org.aurelex.pocket.dictionary"

& $adb shell am force-stop $pkg                                   # REQUIRED, see below

$tmp = Join-Path $env:TEMP "onboarded-false.json"
Set-Content -Path $tmp -Value '{"onboarded":false}' -NoNewline -Encoding ascii
& $adb push $tmp /data/local/tmp/onboarded-false.json
& $adb shell "run-as $pkg cp /data/local/tmp/onboarded-false.json files/settings.json"
& $adb shell rm /data/local/tmp/onboarded-false.json

& $adb shell am start -n "$pkg/.AurelexActivity"                  # onboarding is back
& $adb shell run-as $pkg cat files/settings.json                  # confirm the flag
```

Force-stop first: the app rewrites the whole `settings.json` on every launch
(`EngineController::saveSettings`), so an edit made while it is running is
overwritten at the next save. For the same reason you need **only** the one key
— `loadSettings` keeps its defaults for anything absent and the next save
re-fills the rest (`articleZoom`, `themeMode`, `remoteCatalogUrl`, …), so there
is no need to preserve them.

For the other direction — checking that a returning user is *not* shown the
overlay — push `{"onboarded":true}` the same way.

A fresh install also shows the overlay (there is no upgrade heuristic — see the
`all-qt-ui-port` tasks), so `adb install -r` with cleared data is the other way
to reach the same state. `run-as` needs a debuggable build; on a release APK the
file is not readable this way, so reinstall or clear its data instead.

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

### How it works

- QML strings use `qsTr("…")` with `%1`-style placeholders
  (`qsTr("Indexing (%1 of %2): %3").arg(a, b, c)`); imperative JS strings that
  build WebView HTML (history/favorites chrome) are `qsTr` + `_escHtml`-escaped.
  `Accessible.name` values are deliberately **not** translated — they are the
  stable test IDs documented in `AGENTS.md`.
- C++ user-visible strings use `tr()` — today the three catalog-download messages
  in `EngineController.cpp`. Diagnostic/protocol strings (`gd_* failed (rc=%1)`,
  HTTP status bodies in `ArticleServer`) stay English behind the localized
  "engine error:" banner, and `groupName()`'s `"All"` fallback is a deliberate
  invariant literal (every visible group name resolves by id on the QML side).
- `main.cpp` installs a `QTranslator` at startup from the **primary** entry of
  `QLocale().uiLanguages()` (the Qt Android kit does not compile
  `QGuiApplication::uiLanguages()`): it tries the full locale first
  (`aurelex_ru_RU.qm`) then the language-only code (`aurelex_ru.qm`) from the
  embedded `:/i18n/` resource, then falls back to English (with a `qInfo` line)
  without aborting. Only the primary entry may decide: on Android
  `uiLanguages()` appends every locale the APK ships resources for (en/ru/ja)
  after the primary one, so iterating the whole list let an English-primary
  device fall through to the ru/ja catalog — English is the untranslated base
  and has no `.qm`, so "no catalog for the primary language" must end in
  English, not in a later language's catalog.

### Editing the English source

QML user-visible strings use `qsTr("…")`; C++ ones use `tr("…")`. A Qt catalog
entry is keyed by that literal argument (`<source>`), unlike Android
`strings.xml` where the resource `name` is a language-independent key — so the
code is the only home of the English string and the catalogs are downstream of
it. `Accessible.name` values are never translated (they are the stable test IDs
in `AGENTS.md`).

All translatable strings currently live in **two files**:

- `app/main.qml` — every QML label, dialog/banner copy and WebView chrome word
  (`qsTr`, context `main`)
- `app/EngineController.cpp` — three C++ messages (`tr`, context
  `EngineController`): the catalog-download errors ("The dictionary catalog is
  unavailable.", "Not enough free space.", "The download could not be started.")

`scripts/update-translations.ps1` also scans `app/main.cpp`,
`app/EngineController.hpp`, `app/ArticleServer.cpp` and `app/ArticleServer.hpp`,
so a string added there is extracted too — none of them carry one today. This is
the Qt surface only; the Android strings are the separate, already key-based
`app/android/res/values*/strings.xml` (see "Android-managed strings").

**Finding a string.** Grep the two files above, or — for "does this text already
exist, and where?" — read the catalog: `app/i18n/aurelex.ru.ts` lists every
source string with its `filename`/`line` and context, and `linguist.exe`
(`C:\Qt\6.6.3\msvc2019_64\bin`) opens it as a searchable table. The `.ts` is a
generated inventory, not an editing surface (see the rules below).

1. Write or edit the string in the file for its context, above. Keep `%1`-style
   placeholders (`qsTr("Indexing (%1 of %2): %3").arg(a, b, c)`) — never
   concatenate at the literal site.
2. Extract and compile:
   `pwsh -File .\scripts\update-translations.ps1 -Languages @("ru","ja")`
   `lupdate` updates `app/i18n/aurelex.<lang>.ts` to match the sources and
   drops any message whose source no longer exists (`-no-obsolete`); `lrelease`
   then recompiles the `.qm`. Add `-NoCompile` to refresh the `.ts` only.
   Requires Qt's `lupdate`/`lrelease` (`AURELEX_QT_BASE`/`AURELEX_QT_HOST`
   default to `C:\Qt\6.6.3` / `msvc2019_64`).
3. The changed string is now a `<message>` with an *empty* `<translation>` in
   **every** catalog — no translation carries over, because the key changed.
   Fill it in each one (next subsection). An empty `<translation>` is not an
   error: Qt falls back to the English source and `lrelease` warns.
4. Rebuild and verify the result (see "Switching the display language for
   testing" below).

Two rules follow from source-keying:

- **Never edit `<source>` inside a `.ts`.** Its only true home is the QML/C++
  code; `lupdate` regenerates it, and a hand-edited key just vanishes on the
  next extract.
- A user-visible English change obliges a retranslation of RU and JA in the same
  change (`AGENTS.md`).

### Editing a non-English translation

Use this when the English is correct and only a translation is wrong or missing
— the common manual edit.

1. Edit the `<translation>` element of the matching `<message>` in
   `app/i18n/aurelex.ru.ts` and/or `aurelex.ja.ts`. Find the message by its
   `<source>` text; **do not** edit the `<source>`.
2. Recompile the `.qm`:
   `pwsh -File .\scripts\update-translations.ps1 -Languages @("ru","ja")`
   (re-extracting is harmless when the sources did not change). To re-emit a
   single catalog without touching the `.ts`, `lrelease` alone works:
   `& "C:\Qt\6.6.3\msvc2019_64\bin\lrelease.exe" app\i18n\aurelex.ru.ts -qm app\i18n\aurelex_ru.qm`
3. **Commit the compiled `app/i18n/aurelex_<lang>.qm`.** The `.qm` is the
   shipped artifact — embedded by the `qt_add_resources(aurelex "i18n" ...)`
   block in `app/CMakeLists.txt`; the `.ts` is the editable source.

### Android-managed strings (`res/values*/strings.xml`)

The launcher label, Quick-Settings tile, home-screen widget and notification
text are Android resources, not Qt catalogs. Edit the English default in
`app/android/res/values/strings.xml` and mirror the same value into
`values-ru/` and `values-ja/`. Here the `name` attribute is the key, so the
English lives in one place and only values differ per locale (`app_name` stays
"Aurelex" in every language). The strings resolve via `getString(R.string.*)`
in `StagingService`/`IndexingService`; the indexing-progress template is a
c-format `formatted="false"` resource formatted at runtime
(`%1$d of %2$d: %3$s`).

### Adding a new language

1. Create and translate its catalog:
   `pwsh -File .\scripts\update-translations.ps1 -Languages @("ru","ja","<lang>")`
   (a missing `.ts` is created), then fill in its `<translation>` elements and
   recompile.
2. Add the compiled `.qm` to the `qt_add_resources(aurelex "i18n" ...)` FILES
   list in `app/CMakeLists.txt` — a catalog that is not listed is never
   embedded, so the app can never load it.
3. Add `app/android/res/values-<lang>/strings.xml` (copy the keys from
   `values/strings.xml`) for the Android surfaces.
4. **Add the language code to `resConfigs` in `app/build.ps1`** (currently
   `resConfigs "en", "ru", "ja"`). The build regenerates the Gradle template
   with `resConfig "en"`, which makes aapt2 *strip* any `values-xx` directory
   that is not listed — the strings then ship English-only with no build error.
5. Update the shipped-language list where the docs name it: `AGENTS.md`,
   `README.md`, and the localization rows in `docs/TESTING.md`.

### Switching the display language for testing

The app has **no in-app language switcher** — the display language is whatever
the *process* locale resolves to at startup, so switching means changing a
locale and cold-starting the app.

**Per-app language (Android 13+ / API 33 and newer) is the fastest loop.** It
changes only this app, needs no root, and also re-resolves the Android surfaces
(tile/widget/notification strings):

```powershell
$adb = "C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe"   # or add to PATH
$pkg = "org.aurelex.pocket.dictionary"

& $adb shell cmd locale set-app-locales $pkg --user 0 --locales ru-RU        # or ja-JP / en-US
& $adb shell cmd locale get-app-locales $pkg --user 0                      # confirm what the system stored
& $adb shell am force-stop $pkg                                            # REQUIRED, see below
& $adb shell am start -n "$pkg/.AurelexActivity"
```

`en-US` selects the untranslated English base (there is no `aurelex_en.qm`).
Run this **on its own, only when you are finished**, so that pasting the block
above does not undo the switch before you have looked at the app:

```powershell
& $adb shell cmd locale set-app-locales $pkg --user 0 --locales ""         # back to the device language
```

A relaunch is mandatory: `main.cpp` installs the `QTranslator` once, before the
QML engine loads, and never re-evaluates it (a mid-session locale change is a
documented non-goal in the `2026-09-25-localization` design). `am force-stop`
plus `am start` gives that cold start; a plain `adb install -r` also does.

Confirm the locale actually reached Qt — the same check the localization change
used — rather than trusting the settings screen:

```powershell
& $adb logcat -c; & $adb shell am force-stop $pkg; & $adb shell am start -n "$pkg/.AurelexActivity"
& $adb logcat -d | Select-String "using translation catalog|no matching translation"
```

`using translation catalog: "ru_RU" for primary ui language "ru-RU"` means the
catalog loaded. `no matching translation catalog for …` means the **primary** UI
language has no catalog, so the English base is in use — the correct outcome for
an English or unsupported primary language. Treat it as "the locale did not
apply" only when you were expecting a language that has a catalog.

**Known gap:** the app declares no `android:localeConfig` (there is no
`app/android/res/xml/locales_config.xml`, and AGP 7.4.1 cannot auto-generate
one), so the app is not listed under *Settings → Apps → Aurelex → Language*, and
`cmd locale set-app-locales` may be refused on some builds. Making the system
picker real means adding `res/xml/locales_config.xml` (listing `en`, `ru`,
`ja`) and `android:localeConfig="@xml/locales_config"` on `<application>` —
a manifest-only change, but a user-visible feature, so it goes through an
OpenSpec change rather than a drive-by edit.

**Fallback (any device, incl. pre-13):** change the whole system language in
*Settings → System → Languages & input* and relaunch the app. Doing that over
adb (`setprop persist.sys.locale` + `stop`/`start`) needs root and a reboot, so
it is only practical on an emulator; for a multi-locale sweep an AVD with a
different system language is the cheapest option.
