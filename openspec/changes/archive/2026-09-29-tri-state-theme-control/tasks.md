## 1. Controller: tri-state mode

- [x] 1.1 Replace the `m_userDarkOverride` bool with an int `m_themeMode` (`-1` follow-system, `1` light, `2` dark) plus named constants in `app/EngineController.hpp`; change the Q_PROPERTY from `bool userDarkOverride` to `int themeMode` with `WRITE setThemeMode` / `NOTIFY themeModeChanged`. Renaming rather than widening the range keeps the old "override toward dark" name out of the new code (design D1).
- [x] 1.2 Rewrite `applyEffectiveDark()` to resolve the mode against `m_systemDark` into `m_darkMode` per design D2, leaving the palette / `applySystemBarAppearance()` / `gd_set_dark_mode` / `darkModeChanged` fan-out untouched.
- [x] 1.3 Rewrite `toggleDarkOverride()` as `toggleThemeMode()` cycling Light → Dark → Follow-system → Light (design D3), keeping the existing `qInfo` trace line and updating its label.
- [x] 1.4 Make `setThemeMode` a no-op (no signal, no save) when the value is unchanged or out of range, mirroring how `setArticleZoom` guards its writes.
- [x] 1.5 Load and save `themeMode` in `settings.json`: read `themeMode` if present and in range, else migrate legacy `userDarkOverride`/`darkMode` true → Dark / absent-or-false → Auto (design Migration Plan); write `themeMode` on save.

## 2. QML: control reflects the next tap

- [x] 2.1 Point `Material.theme` (main.qml:29) and every palette alias at `engine.darkMode` alone, since the resolution now happens in the controller (design D2). Grep `main.qml` for remaining `userDarkOverride` / `systemDark` reads and confirm the only intentional ones are the theme button's own bindings.
- [x] 2.2 Bind the dock button's icon to the target of the next tap per design D4: sun while following the system, moon while light, follow-system glyph while dark. Update the "Forces dark (or follows the system theme)" comment on the button.
- [x] 2.3 Extend `Accessible.name` to the three target-state values ("Dark mode" / "Follow system theme" / "Light mode"), keeping them invariant English per the localization house rule.

## 3. Glyph: light_mode_auto

- [x] 3.1 Re-subset `app/res/fonts/MaterialSymbols-Outlined-subset.ttf` from the v374 Material Symbols Outlined font (Google Fonts CSS API) for 0xe2c8, 0xf6f0 and 0xfff00; verify with fontTools that all three codepoints survive and the file stays a few KB (design D6).
- [x] 3.2 Add `"light_mode_auto": 0xfff00` to the `symbolIcon()` map in `app/main.qml`.
- [x] 3.3 Switch `symbolIcon()` from `String.fromCharCode` to `String.fromCodePoint` — U+FFF00 is outside the BMP and `fromCharCode` truncates it to U+FF00, rendering tofu (design D5). Confirm the two existing entries still render.
- [x] 3.4 Normalize the subset's vertical metrics to the classic font's 1.0 em (`hhea`/OS-2 `asc = upm`, `desc = 0`, `USE_TYPO_METRICS` set, `post` underline zeroed). The dock's theme cell renders its icon from this font and its label in the default font inside one Column; the upstream `asc 1056 / desc -96` on `upm 960` gave the icon a 1.2 em line box that pushed the "Theme" label ~11 px below the tab labels (design D6).
- [x] 3.5 Declare the bundled fonts/catalogs with `qt_add_resources` in `app/CMakeLists.txt` instead of `.qrc` files + AUTORCC, and delete the now-unused `fonts.qrc` / `i18n.qrc`. AUTORCC does not emit the files listed *inside* a `.qrc` as dependencies, so a regenerated subset kept stale glyphs in the APK until an unrelated edit forced a rebuild.

## 4. Docs

- [x] 4.1 Update the AGENTS.md accessible-element table's dark-mode-toggle row: `Accessible.name` gains the third value and the documented meaning flips to the target of the next tap (design D4 / Risk 3).
- [x] 4.2 Record the on-device recipe in `docs/TESTING.md`: walk the cycle in both system themes and assert the mode, the control's announced target and the resolved appearance at each step (plus the pinned-ignores-system, live-system-switch, in-place article, restart, and both migration paths).

## 5. Verification

- [x] 5.1 Build and install (`pwsh -File .\app\build.ps1 -Configuration Debug -Install`).
- [x] 5.2 With the system theme light, cycle the button three times and confirm the app chrome and the open article change together, and that the control's name advertises the next tap's target (spec: the resolved theme drives all appearance; design: the control shows the next target).
- [x] 5.3 Repeat with the system theme dark. Note: a fixed 3-state cycle cannot change the appearance on *every* tap — the tap that hands control back to a system already showing the same appearance necessarily does not repaint. See the spec amendment in design D3.
- [x] 5.4 With an article open, switch themes and confirm the article flips in place without losing the looked-up word (spec: the open article switches in place).
- [x] 5.5 Confirm the three glyphs render as icons, not tofu or a blank box, at the dock's 18 px (design Risk 1). This is a visual check only. Found and fixed during this task: the sun rendered `U+FFFD` because `icon()` had no `light_mode` key, and the original sun/moon candidates (`0xe2c8`/`0xf6f0`) were really `folder_open`/`match_word` — "the codepoint has contours in the font" does not verify glyph identity, only that the slot is occupied. Also found and fixed: the subset's un-normalized metrics shifted the label (tasks 3.4 / 5.9). Eyeballed at 18 px: all three read as intended, so the classic `brightness_auto` (`0xe1ab`) fallback is **not** taken.
- [x] 5.6 Confirm each of the three modes has a distinct icon and accessible name in the on-device accessibility tree (spec: each mode has a distinct control appearance).
- [x] 5.7 Migration: with the app stopped, hand-write a settings.json carrying only the legacy `"darkMode": true` and confirm startup is dark and the stored value becomes the Dark mode; repeat with `"darkMode": false` and confirm Auto. Also confirmed an out-of-range `"themeMode": 7` clamps to Auto.
- [x] 5.8 Restart in each of the three modes and confirm the mode (not just the resolved theme) is restored. This caught a real bug: `loadSettings()` runs from the `gd_init` watcher, i.e. after the QML has bound, so it must `emit themeModeChanged()` or the control keeps advertising the default target until the first tap.
- [x] 5.9 Confirm the theme cell's label baseline matches the other dock tabs and the auto glyph matches the sun/moon size, in all three states. Measured on-device: the "Theme" label ink top row is 2270 in every mode, matching Search/Dicts/Groups/Favorites, and the auto glyph's ink band (30-76) equals the sun's. With the un-normalized subset the auto-state label dropped to 99-119 (11 px low) while the classic-font states stayed at 88-107 — so the A/B also demonstrates the fix.
