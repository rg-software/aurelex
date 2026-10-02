## Why

The app can never display English once the RU and JA catalogs are embedded. On
Android, `QLocale::uiLanguages()` returns the primary locale **followed by every
locale the APK ships resources for** (`en`, `ru`, `ja` from `resConfigs`), each
expanded into region/script forms. `app/main.cpp` walked that whole list and
installed the first catalog that loaded; because English is the untranslated base
and has no `aurelex_en.qm`, an English-primary list fell through to the `ru`
catalog. On a device with per-app language set to `en-US` the app started in
Russian (observed on a motorola ThinkPhone, Android 15):

```
using translation catalog: "ru_RU" for "en-US,en-Latn-US,en,ru-RU,ru-Cyrl-RU,ru,ja-JP,ja-Jpan-JP,ja"
```

The same defect is in the catalog display-name lookup
(`Entry::nameFor(QLocale().uiLanguages())`): a device whose primary language the
manifest has no name for could show a secondary (ru/ja) name.

## What Changes

- `app/main.cpp` selects the translation catalog from the **primary** UI
  language only: the full locale (`ru_RU`), then its language code (`ru`), then
  English. A catalog for a language that merely appears later in
  `uiLanguages()` (because the APK ships resources for it) SHALL NOT win.
- `EngineController::refreshCatalogEntries` resolves each catalog entry's
  localized display name from the primary language only, for the same reason.
- The startup `qInfo` lines change slightly to name the primary language
  (`using translation catalog: "ru_RU" for primary ui language "ru-RU"` /
  `no matching translation catalog for "en-US"; using English base strings`).
  `docs/DEVELOPMENT.md` and `docs/TESTING.md` are updated to match, and the
  on-device switch recipe no longer puts the reset command in the same
  copy-paste block as the switch.

No requirement is added or removed: the localization spec already requires the
device's UI-language preference to drive the display language and English to be
the fallback when no catalog matches. This change makes the implementation
conform, and pins the "later list entries must not override the primary" rule as
an explicit scenario.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `localization`: the "Display language follows the device locale" requirement
  gains an explicit scenario that only the primary UI language may select a
  catalog; a later entry in the platform's language list does not.

## Impact

- `app/main.cpp` — catalog selection (startup only).
- `app/EngineController.cpp` — the catalog entry `displayName` call site.
- `docs/DEVELOPMENT.md`, `docs/TESTING.md` — the fallback description, the
  logcat check, and the adb switch recipe.
- No change to `carve/`, `patches/`, the CI smoke test, the catalogs
  (`app/i18n/*`), or the Android string resources. No locale-content change.
