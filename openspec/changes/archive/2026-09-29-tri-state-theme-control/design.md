## Context

See proposal.md — Why. What constrains the approach:

- `EngineController` holds three separate flags: `m_darkMode` (the resolved theme),
  `m_systemDark` (sampled from Android), and `m_userDarkOverride` (the persisted boolean).
  Every one of the ~40 `engine.darkMode` bindings in `main.qml` — palette aliases,
  section stripes, the article CSS injection, the system-bar call — reads the resolved
  value, so that surface must not change shape.
- Qt 6.6's Android QPA does not surface the system night setting; `m_systemDark` is polled
  over JNI from `AurelexActivity.isNightModeActive()` on the existing 500 ms tick. That
  mechanism is unchanged by this work.
- The dock's theme cell is a sibling of the `TabBar` (never an active tab) with a fixed
  18 px glyph over a 10 px "Theme" label, and it must stay that shape.
- The bundled classic `MaterialIcons-Regular.ttf` already carries `light_mode` (0xe518) and
  `dark_mode` (0xe51c). Verified by extracting the GSUB ligature table: both names resolve
  to those codepoints.

## Goals / Non-Goals

**Goals:**

- Replace the boolean with a three-valued mode while leaving every `engine.darkMode`
  consumer untouched, so the diff is confined to the mode plumbing plus the one button.
- Make the button's icon and accessible name a single, testable expression of "what the
  next tap does".
- Migrate persisted settings without changing any existing user's effective theme.

**Non-Goals:**

- A settings screen or a long-press picker. The dock cell stays the only theme control;
  the third state is discoverable from the icon, not from a menu.
- Per-dictionary or per-article theme. The theme is app-wide today and stays app-wide.
- Any engine, carve, or `patches/` change — see Impact in the proposal.
- Localization changes — see the proposal's Impact note for why no catalog is touched.

## Decisions

**D1 — Mode is an int enum on the controller, not a bool.**

`userDarkOverride` (bool) becomes `themeMode` (int): `-1` = follow system, `1` = light,
`2` = dark. Values are the persisted representation, so no separate serialize step.

Rejected: a string ("auto"/"light"/"dark") — self-describing in `settings.json`, which
matters for a file a developer may hand-edit, but it adds a parse/validate path and makes
QML comparisons string-typed. The article-zoom clamp in this same controller already sets
the precedent of a clamped int with an out-of-range fallback, so an int is the
house-consistent choice and the spec's "unrecognized mode falls back to following the
system" scenario falls out of the existing clamp.

Note the naming: `themeMode` rather than reusing `userDarkOverride` with a wider range. The
old name encodes "override toward dark", which is exactly the bias being removed; keeping it
would leave the fix half-named.

**D2 — `darkMode` keeps its current meaning; only `themeMode` is new.**

`applyEffectiveDark()` resolves the mode against `m_systemDark` into `m_darkMode`, and
`m_darkMode` keeps driving the palette, `applySystemBarAppearance()`, `gd_set_dark_mode`,
and `darkModeChanged`. Only the resolution line changes:

```
m_darkMode = m_themeMode == Light ? false
          : m_themeMode == Dark  ? true
          : m_systemDark;
```

This is what keeps the QML diff small: `Material.theme` already reads
`engine.userDarkOverride || engine.systemDark`, and after the change it reads
`engine.darkMode` alone.

Rejected: letting QML resolve the mode (exposing `systemDark` + `themeMode` and doing the
`if` in the binding). It would put the theme rule in a QML string where it is neither
tested nor reused by the C++ side that already needs the resolved value for
`gd_set_dark_mode` and the system bars.

**D3 — Cycle order Light → Dark → Follow-system.**

The original symptom is a control whose tap appears to do nothing: under a dark system,
follow-system already renders dark, so "force dark" changes nothing visible. Ordering the
follow-system state last means the step *out* of follow-system is always an explicit theme,
so the follow-system state — the one that most often renders as a no-op — is never the
*source* of a no-op step.

Correction made during implementation: the earlier draft of this decision claimed the cycle
guarantees that *every* tap changes the appearance. That is not achievable, and the on-device
walk (task 5.2/5.3) disproved it. With three states and two possible appearances, a cycle
must return to its starting state after three taps, so at least one transition per cycle is
appearance-preserving. Under this order that step is Dark → Follow on a dark system, or
Follow → Light on a light system — in both cases the step that *returns control to the
system*, where the system is already showing what the user just left. The user's stored
**mode** and the control's glyph and name still change on that tap, so the control is never
inert and never mislabels itself; only a repaint is absent.

The two ways to remove that last repaint are both worse:

Rejected: cycling follow-system → the opposite of the current theme → the current theme
(adaptive). It has no appearance-preserving step, but the step sequence depends on live
system state, so the button's appearance would change when the phone's theme changed even
though the setting did not. That couples the control's look to something outside the setting
and makes the UIAutomator table harder to state — and it cannot express the intent "pin the
theme I am looking at now" if the system already agrees.

Rejected: making the control a three-way menu instead of a cycle. A menu makes the
"hand control back to the system" state directly reachable and removes the cycle ordering
question entirely, at the cost of replacing one tap with two and changing the control the
accessibility table documents. Worth revisiting if the return-to-system step proves
confusing in real use.

Consequence accepted: from a pinned state the app can be dark while the control shows the
follow-system glyph, which reads correctly under the target convention ("tap to hand
control back") but means the icon is not a display of the current theme. That is the
trade D4 makes deliberately.

**D4 — Icon and accessible name show the target, not the current theme.**

Under D3's cycle each mode has exactly one successor, so "the target of the next tap" is a
function of the current mode alone and is distinct for all three:

| mode | next | icon | `Accessible.name` |
|------|------|------|-------------------|
| Light (`1`) | Dark | `dark_mode` (moon) | "Dark mode" |
| Dark (`2`) | Follow | `light_mode_auto` | "Follow system theme" |
| Follow (`-1`) | Light | `light_mode` (sun) | "Light mode" |

Each mode therefore has a distinct icon *and* name, satisfying the spec's "distinct control
appearance" scenario. Note the meanings have inverted from today: the moon now means "tap to
go dark" (it used to mean "you are dark"), the sun means "tap to go light", and the auto
glyph means "tap to give control back to the system".

Rejected: current-state icons. Pinned-light and follow-system-under-a-light-system both
draw a sun, so the control cannot show whether the app is pinned or tracking — the user
would have to open system Settings to find out, which is the one thing this control exists
to avoid.

Rejected: current-state icons. Pinned-light and follow-system-under-a-light-system both
draw a sun, so the control cannot show whether the app is pinned or tracking — the user
would have to open Settings to find out, which is the one thing this control exists to
avoid.

**D5 — `symbolIcon()` switches to `fromCodePoint`, because the auto glyph is off the BMP.**

The Material Symbols Outlined `light_mode_auto` glyph has exactly one codepoint in the
upstream font, **U+FFF00** (verified against the v374 font from the Google Fonts CSS API;
`brightness_auto` at 0xe1ab is a different, unrelated glyph). U+FFF00 is outside the Basic
Multilingual Plane, so it needs a surrogate pair in UTF-16. `String.fromCharCode(0xfff00)`
truncates its argument to 16 bits and yields U+FF00, which is in the font's cmap (a real
Latin glyph) and would render as tofu — a failure that looks like a missing glyph rather
than an encoding bug.

`fromCharCode` is also the current implementation of `symbolIcon()`; both existing entries
(0xe2c8, 0xf6f0) are in the BMP and are unaffected by the change. Switching the helper to
`String.fromCodePoint` is safe for them and is the only fix that handles the new glyph.

**D6 — Re-subset from the upstream variable font rather than hand-drawing the glyph.**

`app/res/fonts/MaterialSymbols-Outlined-subset.ttf` currently holds exactly 0xe2c8
(`folder_open`) and 0xf6f0 (`match_word`). It is re-subset with those two codepoints plus
0xfff00 (`light_mode_auto`), using the upstream Material Symbols Outlined **variable** font
(the `wght` 400 instance, `upm 960`) and the authoritative
`MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints` list from the
`google/material-design-icons` repository as the name→codepoint source of truth. Result
stays a few KB.

Rejected: the `fonts.gstatic.com/render/.../light_mode_auto.kt` URL. Despite the `.kt`
suffix looking like a font endpoint it returns Compose `ImageVector` **Kotlin source**, not
an sfnt binary, so there is nothing to bundle. It would mean hand-converting path data to
a glyph outline — more code and a permanent second source of truth for this icon.

**D7 — The subset keeps the classic font's 1.0 em vertical metrics, and bundled resources
are declared with `qt_add_resources`.**

The dock's theme cell lays its icon (secondary font) and its "Theme" label (default font)
out in one `Column`. Qt sizes a `Text` by its font's line box, so a font whose metrics
differ from its neighbours' silently moves the sibling: the upstream subset carries
`hhea` ascent 1056 / descent −96 on `upm 960` (a 1.2 em line box) against the classic
Material Icons font's `upm 512`, ascent 512 / descent 0 (1.0 em). At 18 px that dropped the
label ~11 px below the tab labels and displaced the glyph. The rebuild therefore pins the
subset to a 1.0 em line box — `hhea`/OS-2 `asc = upm`, `desc = 0`, `USE_TYPO_METRICS` set,
`post` underline zeroed — leaving the glyph outlines untouched (verified byte-identical).

Second, a resource-declaration defect hid the fix: `fonts.qrc` was fed to AUTORCC, which
does not emit the files listed *inside* a `.qrc` as dependencies of the generated
`qrc_*.cpp`. Regenerating the `.ttf` did not rebuild the resource, so the APK kept the old
glyphs until an unrelated edit forced a rebuild — the A/B that "proved" the old font fine
was measuring a stale APK. `app/CMakeLists.txt` now declares the payloads with
`qt_add_resources(aurelex "fonts" ...)` / `("i18n" ...)`, whose `FILES` entries are real
build inputs; `fonts.qrc` and `i18n.qrc` are deleted.

## Risks / Trade-offs

- **The auto glyph is visually distinct at 18 px** → an early report that it looked *larger*
  than the sun/moon traced to D7's line-box mismatch, not the outline: once the subset's
  metrics match, the auto glyph's ink band equals the sun's exactly (measured on device).
  A residual risk remains that it is a *different design* from the classic sun; verify it
  reads at 18 px. If it does not, the fallback is classic `brightness_auto` (0xe1ab), which
  ships in the already-bundled Material Icons font and needs no sub-setting. Decide on
  device, before archiving.
- **A supplementary-plane codepoint is a new class of bug for this codebase** → the
  `symbolIcon()` helper is the single place a codepoint becomes a string, so D5 fixes it
  once. Add a task to assert the glyph renders rather than tofu.
- **The moon icon's meaning inverts** (it now means "tap to go dark" where it previously
  meant "you are dark") → AGENTS.md's a11y table is updated in the same change so the
  documented contract and the shipped behavior stay in step.
- **`themeMode` is a renamed Q_PROPERTY** → any binding reading `engine.userDarkOverride`
  breaks at runtime, not compile time. There is exactly one such consumer (the dock button),
  but the rename is verified by grep across `main.qml` in the tasks.

## Migration Plan

`settings.json` gains a `themeMode` int key. On load, in order: `themeMode` if present and
in range; else legacy `userDarkOverride`/`darkMode` true → Dark; else Auto.

Note that `saveSettings()` builds a fresh `QJsonObject` and writes only the keys it knows, so
the legacy keys are dropped on the first save after upgrade — the migration is a one-time
read-time translation, not a dual-read-always file. Preserving them would mean teaching
`saveSettings()` to copy through unknown keys, which no other setting does and no requirement
asks for. The rollback consequence is bounded: an older build reading a file with
`themeMode` but no `userDarkOverride` finds no legacy key and falls back to follow-system, so
a downgrade can only lose a pinned theme, never fail to start. A straight revert of the C++
and QML diff is the rollback.
