## 1. Prerequisite: install QtQuick.Controls2 on the android kits

- [ ] 1.1 Check availability: `aqt list-qt windows android --archives 6.6.3 android_arm64_v8a` for `qtquickcontrols2` in the base archives, or `aqt list-qt windows android --modules 6.6.3 android_arm64_v8a` for it as a module.
- [ ] 1.2 Install on `android_arm64_v8a`, `android_x86_64`, and `msvc2019_64` (host). If not available via aqt, install via the Qt online installer or copy the `qml/QtQuick/Controls/` + `libQt6QuickControls2*` from the desktop kit.
- [ ] 1.3 Verify: `qml/QtQuick/Controls/` directory exists in the android kit with `qmldir` + plugin .so files.
- [ ] 1.4 Verify: `import QtQuick.Controls` compiles in a test QML file (add a minimal `Button {}` to the experiment's main.qml, build, deploy, check no "module not installed" error).

## 2. CMake + project wiring

- [ ] 2.1 Add `QuickControls2` to `find_package(Qt6 REQUIRED COMPONENTS ...)` in `experiments/qtquick/CMakeLists.txt`.
- [ ] 2.2 Link `Qt6::QuickControls2` in `target_link_libraries(aurelex_exp ...)`.

## 3. Material style activation

- [ ] 3.1 Set `Material.style` and `Material.theme` in main.qml root:
  ```qml
  import QtQuick.Controls.Material
  ApplicationWindow {
      Material.theme: Material.System  // follows system dark/light
      // Manual override: Material.theme: engine.darkMode ? Material.Dark : Material.Light
  }
  ```
- [ ] 3.2 Remove all hardcoded color ternaries (`engine.darkMode ? X : Y`) from QML — Material handles light/dark automatically.
- [ ] 3.3 Verify on-device: dark mode toggle switches the entire UI palette (not just the article body), light mode restores light colors.

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

## 6. Polish

- [ ] 6.1 Add `ProgressBar` for FTS index building (visible when `engine.buildingFts`).
- [ ] 6.2 Add `FloatingActionButton` on the Dicts pane for "Add dictionaries" (opens the staged-folder scan or SAF flow).
- [ ] 6.3 Add `ToolTip` on the icon buttons (Accessibilty).
- [ ] 6.4 On-device verification: all panes functional, Material animations visible, dark/light switching works, NavigationBar navigation works, no bare-QtQuick primitives remain.