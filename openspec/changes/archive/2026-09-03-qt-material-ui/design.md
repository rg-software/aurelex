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

**D1 — QtQuick.Controls2 is already bundled in the kits.** Verified 2026-09-03:
`android_arm64_v8a/qml/QtQuick/Controls`, full CMake packages
(`Qt6QuickControls2`, `Qt6QuickControls2Material`, `Qt6QuickControls2MaterialStyleImpl`, ...),
and `libQt6QuickControls2_arm64-v8a.so` / `plugins/styles/qandroidstyle` are all
present in the local `C:\Qt\6.6.3` kits (2024-03-19 prebuilds, shipped by the
original full-Qt install; the later aqt module adds layered on top). The aqt
android channel's own archive list is lean and does not carry
`qtquickcontrols2`, but that is irrelevant locally — the kit already has it.
No installation prerequisite. (The original experiment's D8 premise — "carve
subset lacks Controls2" — does not hold for these kits.)

**D1b — Kit origin note.** The kits under `C:\Qt\6.6.3` were originally
installed by the Qt Online Installer (full package set, hence Controls2 for
both desktop + android); later aqt installs layered the extra modules onto
that same root.

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

**D4 — Theme switching: Material built-in palette + JNI system-dark read.**
Remove the `engine.darkMode ? X : Y` ternaries; the Material style drives the
palette. Qt 6.6's Android QPA does not read the system dark-mode setting into
`Material.theme` (the Android dark-mode integration landed in Qt 6.7/6.8), so
"follow system" is implemented the same way the storage access works today:
- Java: `(resources.configuration.uiMode & UI_MODE_NIGHT_MASK)
  == UI_MODE_NIGHT_YES` (or `isNightModeActive()`), surfaced as a C++ bool
  property via `QJniObject`, with the activity's `onConfigurationChanged`
  notifying for live switching.
- Binding: `Material.theme: engine.systemDark ? Material.Dark : Material.Light`.
- The manual D toggle (existing) overrides the system value (user wants dark
  while system light) via a `userDarkOverride` flag.

**D5 — Form components.** Replace all bare-QtQuick primitives:
- `TextInput` → `TextField` (Material outlined or filled)
- `Rectangle` + `Text` + `MouseArea` (button) → `Button` / `RoundButton` / `IconButton`
- `ListView` + `Rectangle` (row) → `ListView` + `ItemDelegate` (with ripple)
- `Text` (label) → `Label` (Material typography)
- `Rectangle` (divider) → `MenuSeparator` / `ToolBar`

**D6 — Material icons (verified against Qt 6.6).** The Qt 6.6 Material style
does NOT provide an `Icons` namespace or an icon font: `plugins.qmltypes` for
`QtQuick.Controls.Material` registers only the attached `Material` type
(`theme`, `primary`, `accent`, `elevation`, `iconColor`, `rippleColor`, ...) —
the `Material.Icons.*` glyph enum from Qt 5 was removed in the Qt 6 port.
So icons must come from an app-supplied source. Two options:

- **(a) Bundle the Material Icons font.** Ship `MaterialIcons-Regular.ttf`
  (Apache-2.0) as a Qt resource, register it with `QFontDatabase`, and render
  the glyph codepoints on `Text`/`IconImage` where a Material font family is set.
  Canonical Material Design 3 look; any density; ~1–2 MB APK cost. Codepoints
  come from the font's official mapping (arrow_back, star / star_border, search,
  library_books, folder, history, bookmark, close, add, delete, dark_mode, ...).
- **(b) Reuse the engine's bundled SVG icon set** (already staged under
  `android/assets/icons/`). Zero new assets, but the icons are GoldenDict's
  style, not Material.

   Recommended: (a) for the app chrome (NavigationBar, IconButton, top-bar
   actions) to get the Material look; (b) remains for in-article chrome where
   the engine's own assets are already referenced by article HTML.

   Prerequisite (a): fetch `MaterialIcons-Regular.ttf`, add to a `.qrc`, expose
   a font family, and map the plan's icon names (arrow_back, star, etc.) to
   codepoints in one QML helper.

### Risks / Trade-offs

- [Resolved] Material style availability on the android kit → Controls2 is already
  present (D1); a straight `find_package` + `import` works.
- [Resolved] Theme switching may not read the Android system dark mode on Qt 6.6 →
  implemented via JNI (D4) instead of `Material.theme: Material.System`.
- [Remaining] The Material restyle is a careful mechanical pass over the current
  QML (which has grown: membership editor, article bridge, confirm dialog,
  storage opt-in). The per-pane task list stays valid; implement against current
  `main.qml`, not older assumptions.
- [Remaining] `Material.theme` toggling does not re-render the WebView article
  by itself — the dark-mode toggle already calls `gd_set_dark_mode` + re-lookups
  (re-emits article CSS); the QML palette switch is handled by Material
  automatically. Keep that behavior.

### Migration Plan

1. Turn on the Material style: `find_package`/link `QuickControls2` (already in
   the kits), `import QtQuick.Controls`, set `Material.theme`.
2. Add the JNI system-dark read + `userDarkOverride`, bind `Material.theme`.
3. Replace primitives pane-by-pane per the task list, using the current QML.
4. Verify on-device: all panes, dark/light switching (system + manual), ripple.

### Open Questions

- None blocking — the distribution blocker is resolved (Controls2 in kit) and
  dark-follow has a concrete JNI path. Remaining decisions are cosmetic
  (icon font vs SVG, D6).