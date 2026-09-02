## Design

### Context

The experiment (`qt-quick-frontend`, archived) used bare-QtQuick because the aqt
carve-subset install didn't ship `QtQuick.Controls2`. The experiment's D8
decision (bare-QtQuick) was a workaround for the install limitation, not an
architectural choice. Now that the all-Qt port is committed (`all-qt-ui-port`),
the UI should look native before the app replaces the Compose UI.

### Goals / Non-Goals

**Goals:**
- Material Design 3 look and feel (ripple effects, elevation, ink highlights)
- Automatic light/dark theme switching (follows system, with manual override)
- Proper form components (`TextField`, `Button`, `ItemDelegate`, `Switch`)
- Navigation via `NavigationBar` or `Drawer` instead of a cycle button
- Minimal code changes (swap imports + replace primitive types with Material equivalents)

**Non-Goals:**
- Changing behavior (dict management, groups, FTS, lookup, history, favorites all stay the same)
- Dynamic color (Material You / wallpaper-based palettes) — follow-up change
- Custom branding / theme colors — use Material defaults for now
- iOS or desktop styling — Android only

### Decisions

**D1 — Install the full Qt android kit.** The aqt carve-subset install was used
to minimize the toolchain during the experiment. For the port, install the full
Qt 6.6.3 android kit (or at minimum, add the `qtquickcontrols2` archive). The
`qt_add_qml_module` + `find_package(Qt6 COMPONENTS QuickControls2)` wiring is
standard. The desktop host kit (`msvc2019_64`) also needs the module for QML
tooling (`qmlcachegen`, `qmllint`).

Alternative considered: community QML Material libraries — rejected (unmaintained,
uncertain Qt 6.6 compatibility).

**D2 — Material style (not Universal).** Material Design 3 is the native Android
look; Universal is a cross-platform compromise. Material gives us:
- `Material.theme: Material.System` (follows system dark/light)
- `Material.primary` / `Material.accent` / `Material.background` — Material palette
- Ripple animations on `Button`, `ItemDelegate`, `ListView`
- `Material.elevation` for cards and toolbars
- Built-in dark/light switching via `Material.theme`

Alternative considered: Universal style — rejected (doesn't feel native on Android).

**D3 — Navigation: `NavigationBar` (bottom) instead of cycle button.** The
current UI uses a single cycle button in the top bar to switch between 6 panes.
This doesn't scale — replace it with a `NavigationBar` (Material bottom bar) or
`Drawer` (side menu) with icons + labels for each pane. This gives:
- One-tap access to any pane (no cycling)
- Visual indicator of the current pane
- Room to add panes without changing the navigation pattern

Alternative considered: keep the cycle button — rejected (doesn't scale, poor UX).

**D4 — Theme switching: Material built-in, not manual palette.** Remove all
`engine.darkMode ? X : Y` ternaries from QML. Instead, set
`Material.theme: Material.System` at the root and let the Material style handle
light/dark switching automatically. The manual toggle (from the shipped app)
overrides `Material.theme: Material.Dark / Material.Light` via a two-way binding.

**D5 — Form components.** Replace all bare-QtQuick primitives:
- `TextInput` → `TextField` (Material outlined or filled)
- `Rectangle` + `Text` + `MouseArea` (button) → `Button` / `RoundButton` / `IconButton`
- `ListView` + `Rectangle` (row) → `ListView` + `ItemDelegate` (with ripple)
- `Text` (label) → `Label` (Material typography)
- `Rectangle` (divider) → `MenuSeparator` / `ToolBar`

### Risks / Trade-offs

- [Material style may not be available on the aqt android install] → Verify by
  installing the `qtquickcontrols2` archive. If unavailable, fall back to the
  full Qt online-installer kit or the Windows desktop kit's `qml/` directory.
- [Material default colors may not match Aurelex branding] → Use Material defaults
  for the experiment; add custom `Material.primary` / `Material.accent` colors in
  the port polish.
- [Material theme switching may not re-render the WebView content] → The dark
  mode toggle already calls `gd_set_dark_mode` + re-looks-up (which re-emits the
  article CSS). The QML palette switching is handled by Material automatically.

### Migration Plan

1. Install `qtquickcontrols2` on the kits (prerequisite).
2. Update `CMakeLists.txt`: add `QuickControls2` to `find_package`.
3. Update `main.qml`: add `import QtQuick.Controls`, set `Material.style`/`Material.theme`, replace all primitives.
4. Verify on-device: all six panes still work, dark/light switching works, Material ripple animations visible.

### Open Questions

- Whether the `qtquickcontrols2` archive is available via `aqt` for android
  arm64-v8a / x86_64 at Qt 6.6.3 (earlier `--archives` listing showed it as a
  base archive; the `--modules` listing showed it as unavailable). May need to
  use the full online-installer kit or build from source.
- Whether the Material style requires a separate `qtquickcontrols2materialstyleimpl`
  archive (it was previously installed but didn't provide the base module).