## Why

Looking up a word should not require opening the app, going to the search
field, and typing. A long-press dictionary user wants one gesture from
anywhere on the phone — the Quick Settings shade or the launcher — to reach a
definition. This change delivers that as a Quick Settings tile (clipboard →
lookup) and a home-screen search widget.

## What Changes

- Add a **Quick Settings tile** (`TileService`) that looks up the current
  clipboard text and opens the article. Tapping the tile routes through a new
  intent action so the (now-foreground) app reads the clipboard itself,
  sidestepping Android 10+ background clipboard restrictions.
- Add a **home-screen search widget** (`AppWidgetProvider`) with a search
  field. Entering a word and confirming it opens the article for that word.
  Tapping the field opens the app's search screen as a fallback.
- Extend `MainActivity`'s existing intent routing (`handleLookupIntent`) with
  `LOOKUP_CLIPBOARD` and widget-search actions so both surfaces reuse the
  current lookup + article + not-found flow.
- Manifest + resources: register the tile (with metadata/label/icon) and the
  widget (receiver + appwidget-info XML).
- Pure Kotlin/manifest/resources. **No engine or boundary changes** — no
  patch pipeline involvement.

## Capabilities

### New Capabilities
- `launcher-shortcuts`: Quick Settings tile and home-screen widget that
  trigger a word lookup from outside the app.

### Modified Capabilities
- none

## Impact

- `app/src/main/AndroidManifest.xml` — `TileService` (with meta-data + label +
  icon) and `AppWidgetProvider` receiver declarations.
- `app/src/main/java/aurelex/android/MainActivity.kt` — new intent actions in
  `handleLookupIntent` for clipboard lookup and widget text lookup.
- New files: `QuickLookupTileService.kt`, `AurelexSearchWidget.kt`
  (AppWidgetProvider), `res/xml/appwidget_info.xml` + tile meta-data,
  `res/drawable/` tile + widget icons, `res/layout/` widget layout, strings.
- No dependency additions; uses `android.appwidget`, `android.service.quicksettings`,
  platform APIs only.