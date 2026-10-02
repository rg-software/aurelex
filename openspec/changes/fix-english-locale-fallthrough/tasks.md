## 1. Root cause

- [x] 1.1 Reproduce on device (motorola ThinkPhone, Android 15): set the app locale to `en-US` and cold-start; logcat shows `using translation catalog: "ru_RU" for "en-US,en-Latn-US,en,ru-RU,ru-Cyrl-RU,ru,ja-JP,ja-Jpan-JP,ja"`
- [x] 1.2 Confirm the app locale reaches Qt (not a per-app-locale / Android-version problem): setting `ja-JP` yields `using translation catalog: "ja_JP" for "ja-JP,..."`
- [x] 1.3 Confirm the list is the primary locale followed by the APK's resource locales (`en`,`ru`,`ja` from `resConfigs`), so the whole-list scan has no terminal English for an English primary

## 2. Catalog selection (design D1, D3)

- [x] 2.1 `app/main.cpp`: select from `QLocale().uiLanguages().value(0)` only — full locale, then language code, then no translator (English)
- [x] 2.2 Keep the full-code → base-code chain so the region-variant case (`pt-BR` → `pt`) still resolves
- [x] 2.3 Update the `qInfo` lines to name the primary language while keeping `no matching translation catalog` greppable

## 3. Catalog display names (design D2)

- [x] 3.1 `EngineController::refreshCatalogEntries`: compute the primary-language list once before the entry loop
- [x] 3.2 Pass it to `Entry::nameFor` instead of the full `QLocale().uiLanguages()`
- [x] 3.3 Confirm `catalog_test`'s `nameFor` checks are unchanged (they pass explicit lists; the function's behaviour is untouched)

## 4. Docs

- [x] 4.1 `docs/DEVELOPMENT.md`: describe primary-language-only selection in "How it works"
- [x] 4.2 `docs/DEVELOPMENT.md`: move the `--locales ""` reset out of the copy-paste switch block and add `en-US` as an example
- [x] 4.3 `docs/TESTING.md`: update the description, the logcat check, and row 52's expected message; add a row for the English-primary regression

## 5. Verification

- [x] 5.1 Host unit tests pass: `article_server_test`, `index_migration_test`, `index_cleanup_test`, `dictionary_index_test`, `staged_cleanup_test`, `staging_rules_test`, `catalog_test` all OK (no host test covers `main.cpp` or QML; `catalog_test` confirms `nameFor` is unchanged)
- [x] 5.2 Build + install, app locale `en-US`, cold start: logcat `no matching translation catalog for "en-US"; using English base strings`, and the visible UI is English (uiautomator dump shows no Russian app chrome)
- [x] 5.3 Set `ja-JP`: `using translation catalog: "ja_JP" for primary ui language "ja-JP"`
- [x] 5.4 Reset to the device language (`ru-RU`): `using translation catalog: "ru_RU" for primary ui language "ru-RU"`
- [x] 5.5 `docs/TESTING.md` row 52a recorded with the observed result
- [x] 5.6 `carve/`, `patches/`, `app/i18n/*`, and the Android resources are untouched; only `app/main.cpp`, `app/EngineController.cpp`, and docs changed
