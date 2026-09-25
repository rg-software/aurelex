## Why

The app is hardcoded English: all UI strings are inline literals in `app/main.qml`
plus a few labels/navigation strings in `app/android/AndroidManifest.xml` and the
Android services. There is no localization, so every user sees English regardless
of the device language. Adding localization lets the app follow the system
preference out of the box and keeps strings maintainable (external, per-language
catalogs instead of literals scattered through QML/HTML/Java).

## What Changes

- Introduce the standard Qt i18n pipeline (QML `qsTr()` / C++ `tr()`, `.ts`
  sources, `.qm` catalogs, `QTranslator` install at startup).
- Move all user-visible strings out of inline literals into per-language
  translation catalogs split by language (one catalog per locale, English as the
  untranslated source/base language).
- Default language follows the device/system locale (first UI language), with a
  sensible fallback chain (full locale → language → English base).
- Ship an initial set of language catalogs (RU, JA) chosen to prove the
  pipeline incl. non-Latin script handling (Cyrillic, Japanese kana/kanji); the
  mechanism supports adding more via a script.
- Localize Android-side user-visible strings (launcher label, QS-tile label,
  widget label, notification titles/text) via `res/values*/strings.xml`, picked
  automatically by Android from the device locale.
- Keep `Accessible.name` values invariant English — they are the documented stable
  test IDs for UIAutomator/Appium (see AGENTS.md); only visible text is localized.

## Capabilities

### New Capabilities

- `localization`: the app follows the device's UI language for all user-visible
  text (QML UI, WebView chrome built in JS, Android labels and notifications),
  with English as fallback, while `Accessible.name` test IDs stay invariant.

### Modified Capabilities

<!-- None: existing capability specs describe behavior that is unchanged. In
     particular `accessibility` is unaffected because Accessible.name values are
     explicitly kept invariant English. -->

## Impact

- `app/main.qml` — every user-visible `text:` literal and the JS-built WebView
  chrome (history/favorites rows, "Clear all", suggestion overlay, banner strings
  like "Preparing dictionaries…") wrapped in `qsTr()`; `Accessible.name` left
  literal.
- `app/main.cpp` — install a `QTranslator` chosen from `QLocale().uiLanguages()`
  at startup (the Qt Android kit lacks `QGuiApplication::uiLanguages()`),
  trying the full locale before the base language.
- `app/EngineController.cpp` — add `tr()` only if the string inventory finds
  user-visible text (logs are not translated); extend if needed.
- `app/CMakeLists.txt` — embed the compiled `.qm` catalogs via qrc.
- `app/android/` — `AndroidManifest.xml` labels and Java notification strings move
  to `res/values/strings.xml` (+ `values-ru`, `values-ja`); Java
  reads them via `getString(R.string.*)`.
- New `app/i18n/` — `.ts` sources and compiled `.qm` catalogs per locale.
- New `scripts/update-translations.ps1` — runs `lupdate` (host kit) to
  extract/merge and `lrelease` to produce `.qm`, mirroring the existing
  `scripts/` tooling style.
- No dependency changes; `lupdate`/`lrelease` ship with the existing Qt host kit.