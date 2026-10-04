## 1. Specs

- [x] 1.1 `openspec/specs/launcher-shortcuts/spec.md`: drop the "Home-screen shortcut widget" requirement and its two scenarios; retitle the purpose line and the active-group scenario to the tile
- [x] 1.2 `openspec/specs/distribution-and-polish/spec.md`: "App icon" covers the launcher, notifications and the Quick Settings tile; rename the scenario
- [x] 1.3 `openspec/specs/localization/spec.md`: "Android-managed surfaces localized" drops the widget label
- [x] 1.4 `openspec validate --specs` — 15 passed, 0 failed

## 2. Code

- [x] 2.1 `AndroidManifest.xml`: remove the `AurelexSearchWidget` receiver and its `appwidget.provider` meta-data
- [x] 2.2 Delete `AurelexSearchWidget.java`
- [x] 2.3 Delete `res/xml/appwidget_info.xml`, `res/layout/widget_search.xml`, `res/drawable/ic_widget_search.xml`
- [x] 2.4 Confirm no remaining reference to `AurelexSearchWidget` / `widget_search` / `ic_widget_search` / `widget_label` / `appwidget` outside `openspec/changes/archive/`

## 3. Strings

- [x] 3.1 Remove `widget_label` + `widget_search` from `res/values/strings.xml`
- [x] 3.2 Mirror the removal in `res/values-ru/strings.xml` and `res/values-ja/strings.xml`
- [x] 3.3 Confirm the Qt catalogs never carried these keys (no `.qm` recompile needed) — `app/i18n/*.ts` has no widget entry

## 4. Docs

- [x] 4.1 `docs/TESTING.md`: section title → "Launcher shortcut (QS tile)"; drop row 36; row 37 → "Tile lookup respects the active group"; row 54 → tile only; known gap #37 and the provenance line stop mentioning the widget
- [x] 4.2 `docs/DEVELOPMENT.md`: drop the "Widget fills search with clipboard" backlog item, the "widget clipboard" example in the engine-vs-QML sentence, and the widget from both Android-surfaces lists
- [x] 4.3 `docs/SIGNING.md`: the app-icon paragraph no longer claims the vector foreground is reused in a widget

## 5. Verification

- [x] 5.1 `AndroidManifest.xml` and all three `strings.xml` parse as XML
- [x] 5.2 Repo-wide grep for widget identifiers returns only Qt Widgets, the `engine/` submodule, and `openspec/changes/archive/` (intentionally untouched)
- [ ] 5.3 Build + install: launcher no longer offers an Aurelex widget; Quick Settings tile and the share/deep-link/PROCESS_TEXT entry points still work
- [ ] 5.4 RU and JA builds: no missing-resource warning for `R.string.widget_label` / `R.string.widget_search` (aapt2 would fail the build if a reference survived, so 5.3 covers this too)
