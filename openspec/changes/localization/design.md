## Context

The app is single-language English: every user-visible string is an inline
literal across `app/main.qml` (QML `text:` props plus the JS that renders
WebView chrome — history/favorites rows, "Clear all", suggestion overlay,
status banners), plus Android labels in `app/android/AndroidManifest.xml` and
notification strings in the Java services. There is no i18n wiring at all
(zero `qsTr`/`tr`, no `.ts`/`.qm`, no `QTranslator`). See proposal.md — Why.

Constraints that shape the approach:

- **Real Qt only** (AGENTS.md golden rule): Qt's own i18n machinery is the
  idiomatic choice, not a home-grown std:: replacement.
- **`Accessible.name` values are a documented contract** for UIAutomator/Appium
  (AGENTS.md + the `accessibility` spec) and must stay invariant English.
- The **carve/engine is never touched** (golden rule): user-visible copy stays
  out of C++ display paths (structured data down, localized text in QML).
- Build is PowerShell-driven (`app/build.ps1`) and the Qt **host** kit
  (`msvc2019_64`) ships `lupdate.exe`/`lrelease.exe`; the android kit may not
  ship the `LinguistTools` CMake package.

## Goals / Non-Goals

**Goals:**

- All app-generated user-visible strings become translatable via standard Qt
  catalogs; English remains the base/source language.
- Display language follows the device's first UI language at startup (full locale
  → language → English).
- Initial catalogs ship for RU and JA to prove the pipeline incl. non-Latin
  script handling (Cyrillic, Japanese kana/kanji).
- Android system surfaces (launcher label, QS tile, widget, notifications)
  follow the device locale via Android string resources with English default.

**Non-Goals:**

- In-app language override settings / runtime switching. The device locale is
  read once at startup; changing it takes effect on the next app launch.
- Translating dictionary article content or engine-generated HTML (dict data,
  not app UI).
- Full-machine translation of every string — only the shipped catalogs are
  reviewed; untranslated source strings fall back to English.

## Decisions

### D1. Standard Qt i18n: `qsTr`/`tr`, `.ts` sources, `.qm` catalogs, `QTranslator`

Wrap QML/JS strings in `qsTr(...)` and install `QTranslator` in `main.cpp`.
This is Qt's native pipeline: QML evaluates `qsTr` against the active
translator, parameters/pluralization are built in (`%1`, `.arg`), and it
mirrors upstream goldendict-ng. **Alternative rejected:** a per-language JSON
resource model driven by a C++/QML `LocaleManager` — more plumbing, no
plural/argument support, and it re-implements what Qt already does;
maintenance burden and mis-positioning (it would live outside the standard Qt
idiom this codebase already follows).

### D2. Locale selection at startup (`main.cpp`)

After `QGuiApplication` construction and before the QML engine loads. The Qt
Android kit does not compile `QGuiApplication::uiLanguages()`, so the code uses
`QLocale().uiLanguages()`:

1. Iterate `QLocale().uiLanguages()` in order (e.g. `pt-BR`, then `pt`) and try
   to load `:/i18n/aurelex_<locale>.qm` → `QTranslator::load` from qrc. For each
   UI language, try the full locale first (`aurelex_pt_BR.qm`) then the
   language-only code (`aurelex_pt.qm`).
2. First successful load is installed and iteration stops.
3. No match → no translator → English base strings are shown.

Load failure is non-fatal (best effort); the app always runs (optionally
log a `qInfo` line on which candidate was tried). This directly implements the
system-preference default with the required fallback chain.

### D3. Catalog placement and embedding: `app/i18n/` + qrc

- `.ts` sources and compiled `.qm` files live in `app/i18n/`: source catalogs
  are `aurelex.<lang>.ts` (e.g. `aurelex.ru.ts`) and compiled catalogs are
  `aurelex_<lang>.qm` (e.g. `aurelex_ru.qm`).
- `.qm` are embedded in the APK via a small `.qrc` added to the app target
  (referenced as `:/i18n/aurelex_ru.qm` etc.).
- **Alternative rejected:** shipping `.qm` under `assets/` and loading from a
  path at runtime — qrc is self-contained, immune to storage-path changes, and
  the Qt-recommended distribution for QML apps.

### D4. Translation tooling as a script, not CMake

Add `scripts/update-translations.ps1`: runs the host kit's `lupdate.exe`
(project files `app/main.qml` + C++ sources) then `lrelease.exe`, honoring the
same `AURELEX_QT_BASE`/`AURELEX_QT_HOST` env-var convention as `app/build.ps1`.
Committed `.qm` files are consumed by D3. **Alternative rejected:** wiring
`qt_add_translations`/`LinguistTools` into CMake — the android kit may not
provide it, and the host-tool path is consistent with the repo's existing
script-based tooling.

### D5. String inventory and wrapping strategy in `main.qml`

- **Pure literals** (`text: "Add dictionaries"`, buttons, dialogs, onboarding,
  empty states, `Accessible.name`-unrelated labels) → `qsTr("...")`.
- **Concatenations** (e.g. `"Group: " + ...`, `"Remove dictionary \"" + x +
  "\"?"`, `"In this group (" + n + ")"`) → `qsTr("Group: %1").arg(x)`,
  `qsTr("Remove dictionary \"%1\"?").arg(x)`, `qsTr("In this group (%1)").arg(n)`.
- **Status banners** ("Preparing dictionaries…", "Scanning dictionaries…",
  `"Indexing (N of M)"`) → `qsTr` with `%1`/`%2`/`%3` args fed from engine data.
- **JS-built WebView chrome** in `main.qml` functions
  (`_renderSuggestOverlay`, history/favorites overlay, "Clear all" row,
  per-row remove titles): `qsTr` is callable from QML JS — wrap the literal
  words there; apply `root._escHtml()` to translated output before it lands in
  HTML so translated strings can't break markup.
- **`Accessible.name` is never wrapped** — stays the literal English values of
  AGENTS.md.

### D6. C++ display strings stay out of C++

Inventory `EngineController.cpp` during implementation; keep C++ emitting
structured data/progress and let QML own the visible copy via `qsTr`. If any
user-visible literal is found on the C++ path (expected: none — the carve and
controller produce data, not chrome), wrap with `tr()` and add the C++ sources
to the `lupdate` input. The carve/engine itself is untouched (golden rule).

### D7. Android system surfaces via string resources

- New `app/android/res/values/strings.xml` (default English) carrying
  `app_name`, `tile_label`, `widget_label`, notification channel names, and
  notification title/text strings, incl. the `%1$d`/`%2$d`/`%3$s` c-format
  indexing-progress template.
- `values-ru`, `values-ja` variants.
- Manifest switches its `android:label`/service/receiver labels to `@string/...`
  (Android picks the locale automatically — no app-side plumbing); Java
  services call `context.getString(R.string.*)`.
- Brand note: `app_name` stays "Aurelex" in all languages; only descriptive
  helper strings (tile/widget/notification copy) are translated.

## Risks / Trade-offs

- **Localized text injected into the WebView** (D5) could break HTML or the
  `data-w`/`data-action` dispatch if a translation contains quotes/angle
  brackets → Every translated string is HTML-escaped and attributes remain
  data-driven; only display words are translated, never the attribute values.
- **`lupdate` mis-parses multi-line JS template/concatenation** and misses or
  mangles a string → Keep each translatable string a single literal with
  numeric placeholders (no spread concatenation at the literal site); review
  the generated `.ts` diff after every extraction.
- **Screen reader announces English `Accessible.name` next to localized text**
  is a known a11y trade-off (invariant test IDs vs fully localized a11y tree)
  → Accepted deliberately (user decision; AGENTS.md contract wins); note in
  docs and revisit when tests are per-locale.
- **Missing translation → English source string shown** → Generic, correct Qt
  fallback; only reviewed catalogs are committed; `lrelease` warns on empty
  translations.
- **CJK glyph rendering depends on the device's system fonts** (Qt's Noto set
  is not shipped by the app) → Android devices generally bundle Noto CJK;
  verify JA catalog (kanji) on-device as part of the acceptance pass.
- **Device-locale change mid-session not applied until relaunch** → Documented
  non-goal; matches Qt QML reality (context reload would be required).

## Migration Plan

Additive and low-risk:

1. Land D5 (qsTr everywhere) + D2 (`QTranslator` install) first — behavior is
   byte-identical for English-only devices.
2. Land D7 (Android string resources) — device behavior unchanged, source
   English identical to today.
3. Land D4/D3 + first catalogs (RU/JA) — only then does visible behavior
   change, and only for those locales.
4. On-device verification: ru/ja devices show localized chrome and Android
   surfaces; other locales and English default unchanged.
   Rollback = revert the catalog/install commit; English behavior never
   depended on it.

## Open Questions

None that would change specs/approach/tasks. Exact translations and the final
inventory of JS-chrome strings are implementation-time details resolved by D5
and the generated `.ts` diff.