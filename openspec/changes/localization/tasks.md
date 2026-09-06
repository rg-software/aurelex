## 1. QML string extraction (`main.qml`)

- [ ] 1.1 Inventory every user-visible string in `main.qml` into a checklist: static `text:` props, dialog/onboarding copy, status banners, and every literal in the JS-built WebView chrome (history/favorites rows, "Clear all", suggestion overlay)
- [ ] 1.2 Wrap static text literals in `qsTr(...)`
- [ ] 1.3 Convert string concatenations (`"Group: " + …`, `"Remove dictionary \"" … ?`, `"In this group (" … ")")` to `qsTr` with `%1` placeholders and `.arg()`
- [ ] 1.4 Convert status banners ("Preparing dictionaries…", "Scanning dictionaries…", `"Indexing (N of M)"`) to `qsTr` templates with numeric args fed from engine data
- [ ] 1.5 Wrap JS WebView-chrome literals in `qsTr` and HTML-escape the translated output via the existing `_escHtml` helper before it lands in HTML
- [ ] 1.6 Confirm every `Accessible.name` stays a literal English string (no `qsTr` inside any `Accessible.name`); grep-verify

## 2. Qt i18n runtime

- [ ] 2.1 Add `QTranslator` install loop in `app/main.cpp` after `QGuiApplication` construction and before the QML engine loads: iterate `QLocale::system().uiLanguages()` trying `:/i18n/aurelex_<lang>.qm`, install the first that loads, fall back to no translator (English)
- [ ] 2.2 Log the resolved catalog (or fallback) via `qInfo`; confirm a failed load is non-fatal

## 3. Catalog tooling and embedding

- [ ] 3.1 Add `scripts/update-translations.ps1` running the host kit's `lupdate.exe` (`app/main.qml` + C++ sources) and `lrelease.exe`, honoring `AURELEX_QT_BASE`/`AURELEX_QT_HOST` like `build.ps1`
- [ ] 3.2 Run the script once to scaffold `app/i18n/aurelex.ru.ts`, `aurelex.ja.ts`; review the generated string diff (`lupdate` could mis-parse JS)
- [ ] 3.3 Create an `app/i18n.qrc` embedding the compiled `aurelex_*.qm` catalogs and add it to the app target in `app/CMakeLists.txt`
- [ ] 3.4 Commit the first compiled `.qm` catalogs (`lrelease` output)

## 4. Initial language catalogs

- [ ] 4.1 Translate the Russian catalog (`aurelex.ru.ts`), including parameterized banners and the WebView-chrome strings
- [ ] 4.2 Translate the Japanese catalog (`aurelex.ja.ts`); verify placeholders survive untouched
- [ ] 4.3 Re-run `lrelease` and confirm no empty/obsolete translation warnings for the shipped catalogs

## 5. Android surfaces

- [ ] 5.1 Create `app/android/res/values/strings.xml` (default English): `app_name`, tile label, widget label, notification channel names, notification title/text, and the c-format indexing-progress template (`%1$d of %2$d: %3$s`)
- [ ] 5.2 Add `values-ru`, `values-ja` variants
- [ ] 5.3 Switch `AndroidManifest.xml` labels (app, QS tile, search widget) to `@string/*` references
- [ ] 5.4 Update the Java services (`StagingService`, `IndexingService`, `AurelexTileService`, `AurelexSearchWidget`) to `context.getString(R.string.*)` for user-visible text
- [ ] 5.5 Confirm the APK packages the locale resource directories (build.ps1 `android/res` copy + aapt2 merge) and spot-check `res/values-ja/values.xml` inside the built APK

## 6. C++ display string inventory

- [ ] 6.1 Grep `EngineController.cpp` for user-visible literals; convert to `tr()` only if any are found and add the C++ sources to the `update-translations.ps1` `lupdate` input
- [ ] 6.2 Confirm zero edits to `engine/` or `carve/` (golden rule)

## 7. Build and verification

- [ ] 7.1 Build a Debug APK (`app/build.ps1`) and confirm no i18n/build regressions
- [ ] 7.2 On a Russian-locale device: QML UI, WebView chrome, launcher/widget/tile labels and notifications render in Russian
- [ ] 7.3 On a Japanese-locale device: same check, incl. CJK glyph rendering
- [ ] 7.4 On an unsupported-locale device (e.g. `fi`): UI shows the English base strings
- [ ] 7.5 `Accessible.name` content-desc values unchanged from the pre-change build (spare a UIAutomator/Appium assertion pass)
- [ ] 7.6 Update `docs/TESTING.md` with locale-verification rows and the `update-translations.ps1` workflow
- [ ] 7.7 Update `docs/DEVELOPMENT.md` with a "Localization" section explaining how to add or modify localized strings: wrap new visible text with `qsTr`/`tr`, avoid concatenation (use `%1` placeholders), keep `Accessible.name` untranslated, run `scripts/update-translations.ps1`, translate in `app/i18n/*.ts`, and commit the `.qm` output