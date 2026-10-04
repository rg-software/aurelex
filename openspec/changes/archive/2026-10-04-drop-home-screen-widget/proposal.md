## Why

The home-screen widget was built in `quick-lookup-shortcuts` as a **partial**
deliverable and was never finished. The archived tasks say so plainly: design D2
records that "`RemoteViews` cannot capture typed text" and chose a
whole-surface tap instead, while `all-qt-ui-port` 8.1 marked it
`[Partial]` — "the widget is a tappable bar (no text input — RemoteViews
limitation)". Two follow-up items were still parked in
`docs/DEVELOPMENT.md`'s backlog ("Widget fills search with clipboard") and
`docs/TESTING.md` #36/#37 were never closed on a device.

The result is a surface that costs a manifest receiver, an `AppWidgetProvider`,
three resource files, two localized strings and a spec requirement, and gives the
user strictly less than the Quick Settings tile next to it: a tile that reads the
clipboard actually looks a word up, whereas the widget only opens the app. It is
also the only launcher surface still shipped that duplicates a job the Share
sheet, `PROCESS_TEXT` and the `aurelex://lookup` deep link already cover.

Shipping it keeps claiming a capability the app cannot deliver, so it is removed
rather than reimplemented.

## What Changes

- **Removed** the "Home-screen shortcut widget" requirement from
  `launcher-shortcuts`, leaving the Quick Settings tile as that capability's
  only surface. The purpose line and the "No dictionary interference" scenario
  stop naming the widget.
- `distribution-and-polish`: the "App icon" requirement covers the launcher, the
  notifications and the Quick Settings tile — the widget is no longer one of its
  render targets.
- `localization`: "Android-managed surfaces localized" drops the widget label;
  the launcher label, tile label and notification strings are the Android-side
  surfaces.
- **Code**: delete the `AurelexSearchWidget` receiver from
  `app/android/AndroidManifest.xml` and remove
  `AurelexSearchWidget.java`, `res/xml/appwidget_info.xml`,
  `res/layout/widget_search.xml` and `res/drawable/ic_widget_search.xml`.
- **Strings**: drop `widget_label` and `widget_search` from
  `res/values/strings.xml` and both `values-ru/` and `values-ja/`. These are
  Android-side resources only — they never appeared in the Qt catalogs
  (`app/i18n/*.ts`), so no `.qm` is recompiled.
- **Docs**: `docs/TESTING.md` retitles the section to "Launcher shortcut (QS
  tile)", drops row 36, retitles rows 37 and 54, and the provenance line stops
  claiming a widget pass; `docs/DEVELOPMENT.md` drops the backlog item and the
  widget from the Android-surfaces lists; `docs/SIGNING.md` stops claiming the
  icon's vector foreground is reused in the widget.
- **Nothing is rewritten under `openspec/changes/archive/`.** The earlier
  changes keep the record that the widget was built and left partial.

No behaviour a user could reach through a documented path is lost: the tile, the
share-sheet entry, the selection-toolbar entry and the `aurelex://lookup` deep
link are untouched.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `launcher-shortcuts`: the "Home-screen shortcut widget" requirement is
  **removed**; purpose and the active-group scenario cover the tile only.
- `distribution-and-polish`: "App icon" covers the launcher, notifications and
  the Quick Settings tile.
- `localization`: "Android-managed surfaces localized" covers the launcher label,
  the tile label and notification strings.

## Impact

- `app/android/AndroidManifest.xml` — one `<receiver>` block removed.
- `app/android/src/org/aurelex/pocket/dictionary/AurelexSearchWidget.java` —
  deleted.
- `app/android/res/xml/appwidget_info.xml`, `res/layout/widget_search.xml`,
  `res/drawable/ic_widget_search.xml` — deleted.
- `app/android/res/values/strings.xml`, `values-ru/strings.xml`,
  `values-ja/strings.xml` — two strings removed each.
- `docs/TESTING.md`, `docs/DEVELOPMENT.md`, `docs/SIGNING.md` — prose.
- `openspec/specs/launcher-shortcuts/spec.md`,
  `openspec/specs/distribution-and-polish/spec.md`,
  `openspec/specs/localization/spec.md` — the three deltas above.
- No change to `carve/`, `patches/`, the CI smoke test, `app/main.qml`, or the
  Qt catalogs.
