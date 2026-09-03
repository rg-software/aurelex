## 1. Prerequisite: confirm QtQuick.Controls2 present in the kits (no install needed)

- [ ] 1.1 Verify `C:\Qt\6.6.3\android_arm64_v8a\qml\QtQuick\Controls` exists with a Material dir + plugin .so (confirmed 2026-09-03; re-verify after any kit churn).
- [ ] 1.2 Same check for `android_x86_64` and `msvc2019_64` (host, for qmllint).
- [ ] 1.3 Verify `libQt6QuickControls2_arm64-v8a.so` / `plugins/styles/qandroidstyle` present in the android kit.
- [ ] 1.4 Sanity: `import QtQuick.Controls` + a minimal `Button {}` compiles and loads on-device (no "module not installed").

## 2. CMake + project wiring

- [ ] 2.1 Add `QuickControls2` to `find_package(Qt6 REQUIRED COMPONENTS ...)` in `experiments/qtquick/CMakeLists.txt`.
- [ ] 2.2 Link `Qt6::QuickControls2` in `target_link_libraries(aurelex_exp ...)`.

## 3. Material style activation

- [ ] 3.1 Set `Material.style` and `Material.theme` in main.qml root:
  ```qml
  import QtQuick.Controls.Material
  ApplicationWindow {
      Material.theme: engine.userDarkOverride ? Material.Dark
        : (engine.systemDark ? Material.Dark : Material.Light)
  }
  ```
- [ ] 3.2 Remove all hardcoded color ternaries (`engine.darkMode ? X : Y`) from QML — the Material palette drives light/dark.
- [ ] 3.3 JNI system-dark read (Qt 6.6 can't detect it natively): Java `configuration.uiMode & UI_MODE_NIGHT_MASK` → C++ `systemDark` property via `QJniObject`, update on the activity's `onConfigurationChanged`; keep a `userDarkOverride` for the manual D toggle. (Pattern: same as `isAllFilesAccessGranted`.)
- [ ] 3.4 Verify on-device: system dark/light switch re-palettes the app; the manual toggle overrides it.

## 4. Replace bare-QtQuick primitives with Material components

- [ ] 4.1 Search pane: `TextInput` → `TextField` (Material outlined); `Rectangle`+`Text`+`MouseArea` (Clipboard button) → `Button`; suggestion `ListView` delegate → `ItemDelegate`.
- [ ] 4.2 Dicts pane: row `Rectangle`+`Row`+`Repeater` → `ItemDelegate` + `RowLayout` with `IconButton`s for Up/Down/Index/Remove.
- [ ] 4.3 Groups pane: new-group `TextInput` → `TextField`; row buttons → `IconButton` / `MenuItem` (in a context menu); active-group highlight via `Material.primary`.
- [ ] 4.4 FTS pane: query `TextInput` → `TextField`; mode selector → `ComboBox`; Search button → `Button` (Material elevated); results → `ItemDelegate`.
- [ ] 4.5 History pane: `Rectangle`+`Text`+`MouseArea` (Clear all) → `Button` (flat, Material danger color); rows → `SwipeDelegate` (swipe-to-remove) + `ItemDelegate` (tap-to-lookup).
- [ ] 4.6 Favorites pane: rows → `SwipeDelegate` (swipe-to-remove) + `ItemDelegate` (tap-to-lookup).
- [ ] 4.7 Article pane: `Rectangle` back button → `IconButton` (arrow_back icon); favorite star → `IconButton` (star icon, Material primary color when active).
- [ ] 4.8 Onboarding overlay: custom `Rectangle` → `Dialog` (full-page, `Material.dialogs: true`).

## 5. Navigation

- [ ] 5.1 Replace the cycle button with a `NavigationBar` (Material bottom bar) with icons: Search (magnify), Dicts (library_books), Groups (folder), FTS (search_in_docs), History (history), Favorites (star).
- [ ] 5.2 Highlight the current pane in the NavigationBar.
- [ ] 5.3 Verify: one-tap access to any pane, no cycling.

## 7. Material icons (design D6)

- [ ] 7.1 Bundle the Material Icons font: download `MaterialIcons-Regular.ttf` (Apache-2.0) into a `qrc`, register with `QFontDatabase`, define the Material icon font family.
- [ ] 7.2 Add a QML icon helper mapping the plan's icon names (arrow_back, star, star_border, search, library_books, folder, history, bookmark, close, add, delete, dark_mode) to font codepoints.
- [ ] 7.3 Use the icon helper on all IconButton/NavigationBar/actions from sections 4.x/5.x (verified on-device glyph rendering).

## 8. Polish

- [ ] 8.1 Add `ProgressBar` for FTS index building (visible when `engine.buildingFts`).
- [ ] 8.2 Add `FloatingActionButton` on the Dicts pane for "Add dictionaries" (opens the staged-folder scan or SAF flow).
- [ ] 8.3 Add `ToolTip` on the icon buttons (Accessibilty).
- [ ] 8.4 On-device verification: all panes functional, Material animations visible, dark/light switching works, NavigationBar navigation works, no bare-QtQuick primitives remain.