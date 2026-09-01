## 1. Manifest and resources

- [ ] 1.1 Declare the Quick Settings tile in `AndroidManifest.xml`: a `<service
      android:permission="android.permission.BIND_QUICK_SETTINGS_TILE">` with
      `android:name=".QuickLookupTileService"` and a meta-data intent-filter
      pointing at the tile label/icon resource.
- [ ] 1.2 Declare the home-screen widget receiver in `AndroidManifest.xml`:
      `AurelexSearchWidget` with `BIND_APPWIDGET` permission and `APPWIDGET_UPDATE`
      receiver intent-filter + meta-data pointing at `res/xml/appwidget_info.xml`.
- [ ] 1.3 Add `res/xml/appwidget_info.xml` (minWidth/minHeight, updatePeriodMillis=0,
      resizeMode horizontal|vertical, label, initialLayout).
- [ ] 1.4 Add tile meta-data resource `res/xml/quick_lookup_tile.xml` (tile label +
      icon).
- [ ] 1.5 Add `res/layout/widget_search.xml` with the search field: an `EditText`
      with `android:imeOptions="actionSearch"` + hint text referencing `@string/`.
- [ ] 1.6 Add the string resources (tile label, widget name, hint text) to
      `res/values/strings.xml`.
- [ ] 1.7 Add tile + widget icons to `res/drawable/` (vector drawables).

## 2. Tile implementation

- [ ] 2.1 Create `QuickLookupTileService.kt` (extends `TileService`): in `onClick`,
      if not locked, call `startActivityAndCollapse()` with an intent carrying
      action `aurelex.android.action.LOOKUP_CLIPBOARD` targeting `MainActivity`.
- [ ] 2.2 Handle unlocked/paused state gracefully (mark tile active only while the
      lookup window is expected; no `qsTile.state` toggling beyond defaults).

## 3. Widget implementation

- [ ] 3.1 Create `AurelexSearchWidget.kt` (`AppWidgetProvider`): in `onUpdate`,
      build RemoteViews, wire the search-field pending intent (action
      `aurelex.android.action.SEARCH`, extras: the entered text) to
      `MainActivity`, and call `appWidgetManager.updateAppWidget`.
- [ ] 3.2 Handle `onReceive`/text-submit: parse the widget id, build a fresh
      RemoteViews (same wiring), and update the widget.

## 4. MainActivity intent routing

- [ ] 4.1 Extend `handleLookupIntent` with a branch for
      `aurelex.android.action.LOOKUP_CLIPBOARD`: read clipboard via
      `viewModel.clipboardText(context)`; if non-blank call `viewModel.lookup(text)`,
      else open the search screen.
- [ ] 4.2 Extend the same handler for `aurelex.android.action.SEARCH`: take the
      text extra; if non-blank call `viewModel.lookup(text)`, else open the search
      screen.
- [ ] 4.3 Ensure both branches reach the article or "not found" state through
      `lookup()` so active-group/history/not-found handling is reused
      (no new lookup logic).

## 5. Verification on device

- [ ] 5.1 Build + install the debug APK on the Motorola ThinkPhone.
- [ ] 5.2 Add the widget to the home screen: confirm the search field renders and
      confirming a word (e.g. "smoke") opens the article.
- [ ] 5.3 Add the tile to Quick Settings: copy text, tap the tile, confirm the
      article for the copied text opens; empty-clipboard case opens the search
      screen.
- [ ] 5.4 Verify tile/widget lookups respect the active group (set a group,
      lookup via widget) and do not alter the active group.
- [ ] 5.5 Verify the widget survives a device rotation/rescale and remains tappable;
      verify the tile stays functional after app restart.

## 6. Wrap-up

- [ ] 6.1 Update `ROADMAP.md` and the OpenSpec change per repo workflow after the
      change is verified and archived (done at archive time).