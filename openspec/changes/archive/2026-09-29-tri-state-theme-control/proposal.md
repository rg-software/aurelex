## Why

The theme control in the bottom dock is a broken promise when the device is in dark
mode. Its icon shows a moon, its accessible name reads "Light mode", and tapping it
changes nothing: the preference is a plain boolean (`userDarkOverride`) meaning "force
dark", and the effective theme is `userDarkOverride || systemDark`. Under a dark system
the first tap sets the override `false → true`, which `true || true` swallows, and the
second tap sets it back. The user is offered light and can never reach it, exactly when
they are most likely to want to.

The root cause is that "follow the system" and "force dark" are the only two states a
boolean can hold, while the user actually wants three: follow the system, force light,
force dark. The control should be a tri-state, and its icon should say what the *next*
tap will do rather than what the current state is.

## What Changes

- Make the theme preference a tri-state — **Auto** (follow the system), **Light**, and
  **Dark** — replacing the current boolean override.
- Cycle the control in the order **Light → Dark → Auto → Light**. This order matters: the
  step out of Auto always lands on an *explicit* theme, so the mode most likely to already
  match the system (Auto) is never the source of a dead-looking tap. (`Auto → Dark → Light`
  would reproduce the original dead-button bug whenever the system is dark.) A 3-state cycle
  cannot repaint on *every* tap — the appearance has only two values — so the one step that
  hands control back to a system already showing the same theme does not repaint. It still
  changes the stored mode and the control's icon, so the button is never inert.
- Show the **target** of the next tap as the icon, not the current state: sun
  (`light_mode`) while in Auto, moon (`dark_mode`) while in Light, and `light_mode_auto`
  while in Dark. Target-state icons are a function of cycle position alone, so the icon
  always states exactly what the next tap does; a current-state icon could not distinguish
  "pinned light" from "Auto while the system is light".
- Keep `Accessible.name` on the target-state convention it already uses, extended to the
  third state: "Dark mode" / "Light mode" / "Follow system theme".
- Migrate existing installs: a persisted `darkMode: true` becomes **Dark**, a persisted
  `darkMode: false` (or an absent key) becomes **Auto**, so nobody's app silently changes
  theme across the upgrade.
- No engine, boundary, or upstream change: `gd_set_dark_mode` already takes the resolved
  boolean, and the article WebView already flips in place via `gdSetDarkMode()`.

## Capabilities

### New Capabilities

<!-- Capabilities being introduced. Use kebab-case for path segments you introduce
     (e.g. user-auth or identity/user-auth) that follow the project's existing
     spec organization. Each creates specs/<capability-path>/spec.md. -->

<!-- None: the theme control is an amendment to behavior already covered by
     `usability-utilities` (settings persistence) rather than a capability of its own.
     Splitting a single dock button into its own capability file would bury it. -->

### Modified Capabilities

- `usability-utilities`: the persisted-preference requirement gains a theme-mode
  tri-state (Auto / Light / Dark) that replaces the dark-mode override, together with the
  cycle order, the target-state icon and accessible-name contract, and the rule that the
  resolved theme — not the raw setting — drives the app chrome, the system bars, the engine
  preference, and the open article.

## Impact

- `app/EngineController.{hpp,cpp}`
  - `userDarkOverride` becomes an int enum (`-1` Auto, `1` Light, `2` Dark); the Q_PROPERTY,
    `setUserDarkOverride`, `toggleDarkOverride`, `saveSettings`, and the settings load
    migration change accordingly.
  - `applyEffectiveDark` resolves `Auto → systemDark`, and `Light/Dark` win outright;
    the `darkMode` property keeps its current meaning (the resolved theme) so every
    existing `engine.darkMode` binding in QML is untouched.
- `app/main.qml` — the dock button's icon binding and `Accessible.name` become
  target-state expressions over the tri-state.
- `app/res/fonts/MaterialSymbols-Outlined-subset.ttf` — re-subset to carry `light_mode_auto`
  (a Material Symbols glyph the classic Material Icons font lacks). `light_mode` (0xe518)
  and `dark_mode` (0xe51c) already exist in the bundled classic font and are not re-subset.
  The `symbolIcon()` codepoint map in `app/main.qml` gains `light_mode_auto`.
- `app/i18n/*.ts`, `app/android/res/values*/strings.xml` — untouched. No user-visible
  English text changes: the dock cell keeps its "Theme" label and the icons are glyphs,
  not strings. `Accessible.name` values are invariant English test IDs by house rule, and
  the three new names follow that convention. `scripts/update-translations.ps1` is
  therefore not needed for this change.
- `AGENTS.md` — the accessible-element table's dark-mode row gains the third state.
- Affected APIs: none. No `gd_*` boundary function is added or changed; `gd_set_dark_mode`
  keeps taking a resolved 0/1.
- Affected dependencies: none. No engine source, no `patches/` entry, no upstream bump;
  `engine/` stays byte-for-byte at the pinned tag.
- Backward compatibility: settings.json is the only persisted surface and the migration is
  in-place; no storage or dictionary state is touched. A settings value outside the enum
  range falls back to Auto, matching the existing out-of-range clamp on article zoom.
