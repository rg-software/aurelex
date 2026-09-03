## Why

The all-Qt port's experiment (`qt-quick-frontend`, archived) used bare-QtQuick
primitives (`Rectangle`, `Text`, `MouseArea`) with hardcoded colors because the
aqt carve-subset install didn't ship `QtQuick.Controls2`. This produced a
functional but non-native-looking UI (blocky buttons, sharp colors, no
animations, no Material Design polish).

For the port to be a credible replacement for the Compose app, the UI needs
native-feeling Material Design 3 components: `Button` with ripple effects,
`TextField` with outlined/filled variants, proper `ListView` with sticky
headers, `NavigationBar` / `TabBar` for pane navigation, `Switch` / `Dialog`
for settings, and automatic **light/dark theme switching** (built into the
Material style — no custom palette code needed).

This change activates the Material Design 3 style that ships with the kits'
already-installed `QtQuick.Controls2`, replaces the bare-QtQuick primitives with
Material Design 3 components, and drives the theme so the app looks native on
Android out of the box.

## What Changes

- **Install/activate `QtQuick.Controls2`** — already present in the local
  `C:\Qt\6.6.3` kits (verified 2026-09-03); wire `find_package` + link, no
  install needed. Cloud builder (B.6/CI) may need the module added when built.
- **Replace all bare-QtQuick UI primitives** with their Material equivalents:
  | Current (bare QtQuick) | Replacement (Material) |
  | --- | --- |
  | `Rectangle` + `Text` + `MouseArea` (button) | `Button` / `RoundButton` |
  | `TextInput` (search field) | `TextField` (outlined, with placeholder) |
  | `ListView` + `Repeater` + `Rectangle` (list rows) | `ListView` + `ItemDelegate` |
  | `Timer` (debounce) | `Timer` (unchanged, already in QtQuick) |
  | Custom dark mode palette (`engine.darkMode ? X : Y`) | `Material.theme: Material.Dark` / `Material.Light` |
  | Cycle button (top bar) | `NavigationBar` or `Drawer` (bottom/side navigation) |
  | Custom onboarding overlay | `Dialog` (full-page) |
  | Hardcoded `#ececec` / `#222222` colors | `Material.background` / `Material.foreground` / `Material.primary` |
- **Activate the Material style**: `Material.theme` follows system (dark/light) by default, with a manual override matching the shipped app's toggle.
- **Add missing UI polish**: `SwipeDelegate` for history/favorites removal, `FloatingActionButton` for add-dictionaries, `ProgressBar` for FTS index building, `TabBar` or `NavigationBar` for the five-pane navigation.
- **Remove D8 (bare-QtQuick) from the design** and replace with: Material Design 3 via `QtQuick.Controls2`, Material style.

No behavior changes — this is purely a UI restyling. All engine functionality
(dict management, groups, FTS, history, favorites, lookup) stays the same.

## Capabilities

### New Capabilities

None — `skip_specs`: pure UI restyling. The behavior contract is unchanged;
only the visual layer changes.

### Modified Capabilities

None.

## Impact

- `experiments/qtquick/main.qml` — rewritten with Material imports + components
- `experiments/qtquick/CMakeLists.txt` — `find_package(Qt6 COMPONENTS ... QuickControls2)` added
- `experiments/qtquick/build.ps1` — no changes needed (the aqt install script adds the module)
- `experiments/qtquick/android/AndroidManifest.xml` — no changes (the theme is set in QML, not the manifest)
- `openspec/changes/all-qt-ui-port/design.md` — D8 (bare-QtQuick) replaced with D9 (Material style via QtQuick.Controls2)
- The aqt android kits (`android_arm64_v8a`, `android_x86_64`) need the `qtquickcontrols2` module installed
- The desktop host kit (`msvc2019_64`) needs it too (for QML tooling)
