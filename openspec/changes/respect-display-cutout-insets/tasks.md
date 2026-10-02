## 1. Read the cutout on the Android side

- [x] 1.1 In `AurelexActivity.java`, add a private helper that returns the
      `DisplayCutout`'s safe insets (`getSafeInsetLeft/Top/Right/Bottom`) from the
      decor view's `getRootWindowInsets()`, guarded by
      `Build.VERSION.SDK_INT >= 28` and returning 0 below (design D3)
- [x] 1.2 Make `getSystemInsetTop()` / `getSystemInsetBottom()` return the **max**
      of the system-bar inset and the corresponding cutout safe inset, keeping the
      existing resource fallback for pre-28 and for a zero inset (design D1)
- [x] 1.3 Add `getSystemInsetLeft()` / `getSystemInsetRight()` with the same shape
      and the same error handling (`Log.w` on failure, 0 as the answer) (design D2)

## 2. Forward the insets to QML

- [x] 2.1 `EngineController.hpp`: declare `Q_INVOKABLE int systemInsetLeft() const;`
      and `systemInsetRight()` beside the existing pair, with a comment noting the
      values are the union of the system-bar and display-cutout insets
- [x] 2.2 `EngineController.cpp`: implement both with the same
      `QJniObject::callStaticMethod<jint>` / `#if defined(Q_OS_ANDROID)` shape,
      returning 0 off Android

## 3. Apply the insets in QML

- [x] 3.1 `app/main.qml`: `ApplicationWindow.color: root.uiBg`, so the inset strip
      at any edge is app background rather than the window's clear colour (design D4)
- [x] 3.2 `_refreshInsets()`: read the two new values, divide by `_insetDpr`, and
      store them as `_insetLeft` / `_insetRight` (design D7)
- [x] 3.3 Add `leftMargin: root._insetLeft; rightMargin: root._insetRight` to the
      shared anchor line of all five panes — `searchPane`, `dictsPane`,
      `groupsPane`, `favoritesPane`, `ftsPane` (design D4)
- [x] 3.4 `navDock.navRow`: give the cell row the same left/right margins while
      `navDock` itself keeps its full-bleed background and height (design D5)
- [x] 3.5 Update the comment on `_insetTop` / `_insetBottom` to say the values are
      unions with the display cutout and that the horizontal pair exists for the
      same reason

## 4. Guard against silent gaps

- [x] 4.1 Grep every `top: topBar.bottom` pane and confirm each carries both
      margins, so a pane added later is caught in review (design Risks)
- [x] 4.2 Confirm no `qsTr` string was added or changed; if one was, run
      `scripts/update-translations.ps1` and update `values-ru` / `values-ja` in the
      same change
- [x] 4.3 `openspec validate respect-display-cutout-insets --strict` passes
- [x] 4.4 `pwsh -File .\app\build.ps1 -Configuration Debug` + `adb install -r`, and
      confirm the QML compiles with no new warnings

## 5. On-device verification (not claimed fixed until this passes)

Device: Motorola ThinkPhone, Android 15, 1080×2400. Measurement method: read the
platform's insets with `dumpsys window displays` (grep `type=statusBars`,
`type=navigationBars`, `type=displayCutout`) and read the app's layout with
`uiautomator dump` bounds, then compare the outermost interactive element's
bounds against the cutout rect. Screenshots cannot be read directly here, so the
comparison is done on numbers.

Baseline to beat (measured before the change): landscape
`displayCutout frame=[0,0][110,1080]`, hole `Rect(0,510 - 110,570)`; the article's
a11y bounds start at `x = 33`, i.e. **under** the camera.

- [x] 5.1 Portrait: the camera area is covered by the non-interactive top strip and
      `_insetTop` still equals the full cutout height (110 px) — the change must be
      a no-op here
- [x] 5.2 Landscape (rotate from portrait, camera on the left): the article, the
      search field and the dock's outermost tab cell all start at or after
      `x = 110` in device px — i.e. no a11y node overlaps the cutout rect
- [x] 5.3 Landscape the **other** way (`user_rotation 3`, camera on the right): the
      right-hand cells clear the cutout, and the left edge is *not* inset (proves
      the values are per-edge, not symmetric)
- [x] 5.4 Cold start with the device already in landscape: the clearance is correct
      on the first frame, with no rotation event
- [x] 5.5 Rotate back to portrait: no leftover horizontal inset (the side margins
      return to 0) and the top strip still covers the camera
- [x] 5.6 No regression on the other panes: the Dictionaries, Groups, Favorites and
      Full-text search panes are inset identically and the catalog pane and group
      membership editor inherit it
- [x] 5.7 IME regression guard: with an article open, focus the field — suggestions
      still appear and the article is not disturbed (the inset path must not fire on
      a height-only resize)
- [x] 5.8 Both themes: check the inset strip at each edge in light and dark — it must
      be indistinguishable from the neighbouring background
- [x] 5.9 `adb logcat` over the pass: no new warnings from the app's pid, no ANR

## 6. Documentation

- [x] 6.1 `docs/TESTING.md`: add rows for "rotate with an article open on a cutout
      device" (including the right-edge rotation) so the symptom is searchable
- [x] 6.2 Note in `docs/TESTING.md` that portrait is unchanged by design, so a
      future report of "the camera area looks different in portrait" is not a
      regression

## 7. Found and fixed during verification (was NOT in the original plan)

- [x] 7.1 `EngineController::pollInsets()` — read the four insets on the existing
      ~2Hz poll, compare against the previous tick, emit `insetsChanged()` on any
      movement. QML re-reads on that signal. See "Verification findings" below.

## Verification findings

Measured on a ThinkPhone (Android 15, 1080×2400, density 2.5). The platform's
frames come from `dumpsys window displays`; the app's layout comes from
`uiautomator dump` bounds, which are in the same device pixels.

| case | cutout frame | expected | measured |
|---|---|---|---|
| portrait | `[0,0][1080,110]` | no side inset | article `x0=33` PASS |
| landscape, camera left (`rotation 1`) | `[0,0][110,1080]` | left inset 110 | article `x0=142` PASS |
| landscape, camera right (`rotation 3`) | `[2290,0][2400,1080]` | right inset 110 | article `x1=2256` PASS |
| flip `rotation 1` -> `rotation 3` | moves sides, size unchanged | inset follows | right clearance 144 px PASS |
| flip `rotation 3` -> `rotation 1` | moves back | inset follows | left clearance 142 px PASS |
| cold start already in `rotation 3` | `[2290,0][2400,1080]` | correct on first frame | right clearance 144 px PASS |
| back to portrait | `[0,0][1080,110]` | margins return to 0 | article `x0=33` PASS |

Other panes in `rotation 3` (tapped at their real a11y centres, not guessed
coordinates — the first attempt tapped outside the tab and reported three false
"not present" readings): Dictionaries / Groups / Full-text search / Favorites all
report `x0=33 x1=2256`, i.e. they inherit the inset.

Inset strips match the app background exactly in both themes: light `#FFFBFE`,
dark `#1C1B1F`, sampled at the left strip, the right strip and the top strip. The
article canvas differs from the app background — `#FFFFFF` vs `#FFFBFE` light,
`#242526` vs `#1C1B1F` dark — because the WebView paints its own `--gd-bg`
constant (`EngineController.cpp`, set by `gdSetDarkMode`). That difference
predates this change and is unrelated to the cutout work; see "Known cosmetic
difference" in `docs/TESTING.md`.

Two measurement traps hit during this pass, both of which produce a
false PASS if unnoticed:

- **`am force-stop` resets `user_rotation` to 0 on this device.** A "cold start
  already in landscape" run that sets the rotation *before* the force-stop tests
  portrait instead, and then passes trivially. Order must be: force-stop, set
  rotation, confirm the cutout frame is landscape, then launch.
- **The theme cell's position depends on the dock layout.** Its a11y bounds were
  `1909..2290` in `rotation 3`, so a tap at a guessed `x=1950` landed on the
  boundary and silently did nothing. Read the bounds, then tap the centre.

### The bug this found

The first implementation re-read the insets from `onWidthChanged` /
`onHeightChanged` only. `rotation 1` and `rotation 3` are both 2400×1080, so a
flip between the two landscape orientations — the natural way to turn a phone
sideways — fires neither signal, while the display cutout moves from one side
edge to the other. Measured before the fix: the platform reported the cutout
correctly (`sideHint=RIGHT`, `frame=[2290,0][2400,1080]`) but the layout kept the
stale left margin of 142 px and put the article back under the camera on the
right. `rotation 3` -> `rotation 0` does resize, which is why only that direction
appeared to work.

Fixed by polling the inset values themselves rather than listening for a resize,
which also covers the IME, split screen and a foldable unfolding — none of which
are guaranteed to resize the window either. The resize hooks are kept as a fast
path so the common rotation stays instant rather than waiting up to one poll
interval.
