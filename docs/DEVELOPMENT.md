# Development

Everything a contributor (human or AI agent) needs to build, run, and extend
Aurelex. If you are a user, see the top-level `README.md` instead.

## Repo layout

- `engine/` — goldendict-ng submodule, pinned at a release tag, **never edited in place**.
- `patches/` — the only deviations from upstream (`.patch` files), applied by `scripts/apply-patches.*`.
- `carve/` — the `gd_*` C boundary (`goldendict.h`, `gd_boundary.cc`) + selected engine
  sources compiled once as an object library, shared by the Qt app and the CI smoke tool.
- `app/` — the Qt app (QML + WebView, Android) that consumes the carve in-process.
- `openspec/` — planning artifacts (proposals, specs, design, tasks); the design is the source
  of truth for scope.
- `docs/` — in-repo guidance: `TESTING.md`, `SIGNING.md`, `ROADMAP.md`, `UPSTREAM.md`,
  `KAIKKI-CONVERSION.md`.
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

## Engine smoke test

`carve/` builds a host smoke tool (`AURELEX_BUILD_SMOKE=ON`) exercised by
`.github/workflows/engine-smoke.yml` on every engine/patch/carve change: it scans a fixture
folder (including a nested-subfolder fixture, asserting recursion), looks up a known word, and
checks FTS + group/remove behavior. Any upstream bump must keep the smoke green.

## Upstream & maintenance

Upstream is pulled in as a Git submodule pinned to a release tag; only a small patch set
deviates, and the CI smoke verifies each upstream update. See `docs/UPSTREAM.md` for the pin,
update procedure, and patch-application details.

## OpenSpec workflow

Planning artifacts live in `openspec/`. Features/fixes flow through changes:

1. `openspec new change <name>`
2. Draft proposal → design → specs → tasks (default `spec-driven` schema).
3. Implement via the OpenSpec apply workflow.
4. Verify on-device, archive, then update `docs/ROADMAP.md`.

See `docs/ROADMAP.md` for the milestone tracker and cut register.

## Testing

Manual verification recipes live in `docs/TESTING.md` (build/install, lookup, article rendering,
audio, groups, FTS, history/favorites, storage, external entry points).

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
   are embedded via `app/i18n.qrc`.
5. If a new system language is added, also extend `app/android/res/values-xx/`
   (app label, tile/widget labels, notification strings) and add it to the
   `-Languages` array.

Android notification/launcher strings resolve via `getString(R.string.*)` in
`StagingService`/`IndexingService`; the indexing-progress template is a c-format
`formatted="false"` resource formatted at runtime (`%1$d of %2$d: %3$s`).