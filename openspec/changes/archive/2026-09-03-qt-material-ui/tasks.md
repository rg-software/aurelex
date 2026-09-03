## 1. Prerequisite: confirm QtQuick.Controls2 present in the kits (no install needed)

- [x] 1.1 Verify `C:\Qt\6.6.3\android_arm64_v8a\qml\QtQuick\Controls` exists with a Material dir + plugin .so (confirmed 2026-09-03; re-verified on kit, Material dir + qtquickcontrols2plugin .so present).
- [x] 1.2 Same check for `android_x86_64` and `msvc2019_64` (host, for qmllint).
- [x] 1.3 Verify `libQt6QuickControls2_arm64-v8a.so` / `plugins/styles/qandroidstyle` present in the android kit.
- [x] 1.4 Sanity: `import QtQuick.Controls` + a minimal `Button {}` compiles and loads on-device (no "module not installed"). **Satisfied** — the whole app runs on QtQuick.Controls/Material on-device (verified throughout on-device testing).

## 2. CMake + project wiring

- [x] 2.1 Add `QuickControls2` to `find_package(Qt6 REQUIRED COMPONENTS ...)` in `experiments/qtquick/CMakeLists.txt`.
- [x] 2.2 Link `Qt6::QuickControls2` in `target_link_libraries(aurelex_exp ...)`.

## 3. Material style activation

- [x] 3.1 Set `Material.style` and `Material.theme` in main.qml root:
  ```qml
  import QtQuick.Controls.Material
  ApplicationWindow {
      Material.theme: (engine.userDarkOverride || engine.systemDark)
                      ? Material.Dark : Material.Light
  }
  ```
- [x] 3.2 Remove all hardcoded color ternaries (`engine.darkMode ? X : Y`) from QML — the Material palette drives light/dark (replaced by `uiBg`/`uiCard`/&c. aliases reading `Material.*`).
- [x] 3.3 JNI system-dark read (Qt 6.6 can't detect it natively): Java `configuration.uiMode & UI_MODE_NIGHT_MASK` → C++ `systemDark` property via `QJniObject`, update on the activity's `onConfigurationChanged`; keep a `userDarkOverride` for the manual D toggle. (Pattern: same as `isAllFilesAccessGranted`.)
- [ ] 3.4 Verify on-device: system dark/light switch re-palettes the app; the manual toggle overrides it.

## 4. Replace bare-QtQuick primitives with Material components

- [x] 4.1 Search pane: `TextInput` → `TextField` (Material outlined); `Rectangle`+`Text`+`MouseArea` (Clipboard button) → `Button`; suggestion `ListView` delegate → `ItemDelegate`.
- [x] 4.2 Dicts pane: row `Rectangle`+`Row`+`Repeater` → `ItemDelegate` + `RowLayout` with Up/Down/Index/Remove. (Qt 6.6 has no `IconButton`; used `ToolButton` — see design deviation.)
- [x] 4.3 Groups pane: new-group `TextInput` → `TextField`; row actions → `ToolButton` + a `Menu`/`MenuItem` context menu; active-group highlight via `Material.primary`. (Qt 6.6 has no `IconButton`; used `ToolButton`.)
- [x] 4.4 FTS pane: query `TextInput` → `TextField`; **dropped the mode selector `ComboBox`** — Wildcards (`FTS::SearchMode=2`) is the only v1 mode: it parses `read*` prefixes and matches a plain term exactly, so Xapian-syntax/Plain/Regexp are cut (see `full-text-search` spec "Search with wildcards"); Search button → `Button` (Material elevated); results → `ItemDelegate`.
- [x] 4.5 History pane: `Rectangle`+`Text`+`MouseArea` (Clear all) → `Button` (flat, Material danger color); rows → `SwipeDelegate` (swipe-to-remove) + tap-to-lookup.
- [x] 4.6 Favorites pane: rows → `SwipeDelegate` (swipe-to-remove) + tap-to-lookup.
- [x] 4.7 Article pane: back button → `ToolButton` (arrow_back icon); favorite star → `ToolButton` (star/star_border icon, `Material.primary` when active). (Qt 6.6 has no `IconButton`; used `ToolButton`.)
- [x] 4.8 Onboarding overlay: custom `Rectangle` → `Dialog` (full-page, `modal: false` + `NoAutoClose`).

## 5. Navigation

- [x] 5.1 Replace the cycle button with a bottom bar with icons: Search (search), Dicts (library_books), Groups (folder), FTS (history), History (history), Favorites (star). (Qt 6.6 has no `NavigationBar`; used a bottom `TabBar` with 6 `TabButton`s — see design deviation.)
- [x] 5.2 Highlight the current pane in the bottom bar (`highlighted` on the active `TabButton`, driven off `root.state`).
- [x] 5.3 Verify: one-tap access to any pane, no cycling. **Verified on-device** — all 6 bottom tabs fire `_navTo` with the correct pane index.

## 7. Material icons (design D6)

- [x] 7.1 Bundle the Material Icons font: download `MaterialIcons-Regular.ttf` (Apache-2.0) into a `qrc` (`fonts.qrc`, prefix `/fonts`), register with `QFontDatabase`, define the Material icon font family (`"Material Icons"`).
- [x] 7.2 Add a QML icon helper mapping the plan's icon names (arrow_back, star, star_border, search, library_books, folder, history, close, add, delete, dark_mode) to font codepoints.
- [x] 7.3 Use the icon helper on all icon buttons/bottom-bar/actions from sections 4.x/5.x. **Code done** (helper used on dark toggle, back, star, all 6 tabs); on-device glyph rendering verified (`bottombar lightGlyphRatio` pixel check showed icons render).

## 8. Polish

- [x] 8.1 Add `ProgressBar` for FTS index building (visible when `engine.buildingFts`).
- [x] 8.2 Add an `Add dictionaries` action on the Dicts pane. (Qt 6.6 has no `FloatingActionButton`; used a `RoundButton` `highlighted` — see design deviation. Handles the SAF/external-storage flow: opens settings when access not granted, else rescan.)
- [x] 8.3 Add `ToolTip` on the icon buttons (Accessibility): present on the dark-mode toggle, article back, and article favorite-star ToolButtons.
- [ ] 8.4 On-device verification: all panes functional, Material animations visible, dark/light switching works, NavigationBar navigation works, no bare-QtQuick primitives remain.