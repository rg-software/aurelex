## 1. QML string extraction (`main.qml`)

- [x] 1.1 Inventory every user-visible string in `main.qml` into a checklist: static `text:` props, dialog/onboarding copy, status banners, and every literal in the JS-built WebView chrome (history/favorites rows, "Clear all", suggestion overlay)
- [x] 1.2 Wrap static text literals in `qsTr(...)`
- [x] 1.3 Convert string concatenations (`"Group: " + …`, `"Remove dictionary \"" … ?`, `"In this group (" … ")")` to `qsTr` with `%1` placeholders and `.arg()`
- [x] 1.4 Convert status banners ("Preparing dictionaries…", "Scanning dictionaries…", `"Indexing (N of M)"`) to `qsTr` templates with numeric args fed from engine data
- [x] 1.5 Wrap JS WebView-chrome literals in `qsTr` and HTML-escape the translated output via the existing `_escHtml` helper before it lands in HTML
- [x] 1.6 Confirm every `Accessible.name` stays a literal English string (no `qsTr` inside any `Accessible.name`); grep-verified no matches; remaining literals are the non-visible Window `title` ("Aurelex") and the group-row "..." overflow affordance

## 2. Qt i18n runtime

- [x] 2.1 Add `QTranslator` install loop in `app/main.cpp` after `QGuiApplication` construction and before the QML engine loads: iterate `QLocale().uiLanguages()` trying the full locale (`:/i18n/aurelex_<locale>.qm`) then the base language, install the first that loads, fall back to no translator (English)
- [x] 2.2 Log the resolved catalog (or fallback) via `qInfo`; confirm a failed load is non-fatal

## 3. Catalog tooling and embedding

- [x] 3.1 Add `scripts/update-translations.ps1` running the host kit's `lupdate.exe` (`app/main.qml` + C++ sources) and `lrelease.exe`, honoring `AURELEX_QT_BASE`/`AURELEX_QT_HOST` like `build.ps1`
- [x] 3.2 Run the script once to scaffold `app/i18n/aurelex.ru.ts`, `aurelex.ja.ts`; reviewed — lupdate extracted 50 sources incl. the JS-built chrome correctly; found + fixed a stray-quote bug in the remove-dialog string (`"Remove dictionary "%1?""` → `"Remove dictionary "%1"?"`)
- [x] 3.3 Create an `app/i18n.qrc` embedding the compiled `aurelex_*.qm` catalogs and add it to the app target in `app/CMakeLists.txt`
- [x] 3.4 Commit the first compiled `.qm` catalogs (`lrelease` output)

## 4. Initial language catalogs

- [x] 4.1 Translate the Russian catalog (`aurelex.ru.ts`), including parameterized banners and the WebView-chrome strings
- [x] 4.2 Translate the Japanese catalog (`aurelex.ja.ts`); placeholders (`%1`–`%3`) verified untouched in both catalogs
- [x] 4.3 Re-run `lrelease` and confirm no empty/obsolete translation warnings — 50 finished / 0 unfinished per catalog, no warnings

## 5. Android surfaces

- [x] 5.1 Create `app/android/res/values/strings.xml` (default English): `app_name`, tile label, widget label, notification channel names, notification title/text, and the c-format indexing-progress template (`%1$d of %2$d: %3$s`); also covered the widget's visible `Search Aurelex` text
- [x] 5.2 Add `values-ru`, `values-ja` variants
- [x] 5.3 Switch `AndroidManifest.xml` labels (app, QS tile, search widget) to `@string/*` references
- [x] 5.4 Update the Java services (`StagingService`, `IndexingService`) to `context.getString(R.string.*)`; `AurelexTileService`/`AurelexSearchWidget` confirmed to have no user-visible literals (only log lines)
- [x] 5.5 Confirm the APK packages the locale resource directories — aapt2 dump currently strips them (`resConfig "en"` from androiddeployqt's template stripped `values-ru`/`values-ja` at merge); patched build.ps1 to rewrite `resConfig "en"` → `resConfigs "en", "ru", "ja"` on every run; confirmed `(ru)`/`(ja)` configs for all strings in the built APK

## 6. C++ display string inventory

- [x] 6.1 Grep `EngineController.cpp` for user-visible literals — only technical diagnostics (`gd_* failed (rc=%1)`, HTTP status bodies in `ArticleServer`), kept untranslated behind the localized "engine error:" banner; `groupName()`'s `"All"` fallback WAS user-visible (history/favorites) and converted to `tr("All")`; C++ sources already in the `lupdate` input; new `EngineController` context translated (Все / すべて)
- [x] 6.2 Confirm zero edits to `engine/` or `carve/` (golden rule) — verified via `git status`: no engine/carve paths modified

## 7. Build and verification

- [x] 7.1 Build a Debug APK (`app/build.ps1`) and confirm no i18n/build regressions — two failures fixed: `QGuiApplication::uiLanguages()` doesn't exist on the Qt Android kit (switched to `QLocale().uiLanguages()`); `resConfig "en"` template stripped locale resources (see 5.5)
- [x] 7.2 On a Russian-locale device: `adb logcat` shows `[aurelex] using translation catalog for ru-RU,…`; uiautomator dump shows Russian UI text live (hint label) and English `content-desc` on all interactive elements; visual pass pending user (model cannot read screenshots)
- [ ] 7.3 On a Japanese-locale device: same check, incl. CJK glyph rendering — deferred to release testing (no JA device available; catalogs built, packaged, logcat-verified load path on ru catalog)
- [ ] 7.4 On an unsupported-locale device (e.g. `fi`): UI shows the English base strings — deferred to release testing (catalog-load failure path is symptom-less English fallback by design)
- [x] 7.5 `Accessible.name` content-desc values unchanged from the pre-change build — uiautomator dump on the installed RU build: `"Main navigation"`, `"Search"`, `"Dictionaries"`, `"Groups"`, `"Full-text search"`, `"Favorites"`, `"Light mode"`/`"Dark mode"`, `"Add group"`, `"Add"`, `"By Pair"`, `"Remove"`, `"Dictionaries list"` all English (informational labels correctly announce translated text for screen readers)
- [x] 7.6 Update `docs/TESTING.md` with locale-verification rows and the `update-translations.ps1` workflow
- [x] 7.7 Update `docs/DEVELOPMENT.md` with a "Localization" section explaining how to add or modify localized strings: wrap new visible text with `qsTr`/`tr`, avoid concatenation (use `%1` placeholders), keep `Accessible.name` untranslated, run `scripts/update-translations.ps1`, translate in `app/i18n/*.ts`, and commit the `.qm` output