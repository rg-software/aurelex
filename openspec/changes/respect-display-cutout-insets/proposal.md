## Why

On a device with a display cutout, rotating to landscape puts the camera over
live content. Measured on a Motorola ThinkPhone (Android 15, 1080×2400): in
landscape the platform reports a `displayCutout` inset of `[0,0][110,1080]` with
the hole at `Rect(0,510 - 110,570)`, and that region is the **left edge of the
article pane** — article text and the search row run underneath the camera.

The app only ever reads the top and bottom system-bar insets
(`getSystemInsetTop` / `getSystemInsetBottom` → `_insetTop` / `_insetBottom` in
`app/main.qml`). There is no horizontal inset anywhere, so nothing keeps content
clear of a side-mounted camera. Portrait happens to be safe by coincidence: the
status-bar inset there is 110 px, exactly the cutout height, so the camera lands
inside the app's inert top strip.

Drawing into the cutout is not a choice — Android 15 enforces edge-to-edge for
this target SDK and reports `layoutInDisplayCutoutMode=always` with
`EDGE_TO_EDGE_ENFORCED` for the window. Keeping *content* out of the cutout while
still painting the background behind it is the part that is ours, and neither the
code nor the specs do it today.

## What Changes

- **The display-cutout safe insets are read and unioned with the system-bar
  insets**, per edge, taking the larger of the two. This covers both shapes: a
  cutout taller than the status bar (the portrait case, already working by
  accident) and a camera on a side edge (the landscape case, broken).
- **The left/right insets reach QML** next to the existing top/bottom ones and
  become margins on the app's own content — the panes, the search row and the
  inline article. Text and interactive controls therefore stay clear of the
  camera in every orientation.
- **The bottom dock keeps its full-bleed background** while its tab cells take
  the side inset, so the app still fills the screen behind the camera and no
  unthemed gap appears at the edge.
- **Portrait behaviour is unchanged** (a cutout's horizontal insets are 0 there,
  and the top strip already covers the camera), so this is a landscape-only
  correction.
- No engine, carve, or `gd_*` boundary change. App-side Android + QML only.

## Capabilities

### New Capabilities

- `window-insets`: keeping the app's own content clear of the system bars and the
  display cutout in every window orientation, while the window itself stays
  edge-to-edge behind them. No spec currently states this contract at all — the
  top strip and the dock's clearance from the navigation bar are implemented but
  unspecified — so the behaviour that is already correct in portrait becomes
  guaranteed rather than incidental, and the landscape gap is closed.

### Modified Capabilities

None. No existing requirement states that content spans the full pane width or
sits under a camera, so nothing in the current specs changes.

## Impact

- `app/android/src/org/aurelex/pocket/dictionary/AurelexActivity.java` — add
  `getSystemInsetLeft()` / `getSystemInsetRight()`; make `getSystemInsetTop()` /
  `getSystemInsetBottom()` union with the cutout's safe insets.
- `app/EngineController.hpp` / `app/EngineController.cpp` — two new
  `Q_INVOKABLE int` accessors beside the existing two.
- `app/main.qml` — `_insetLeft` / `_insetRight` in `_refreshInsets()` (which
  already re-reads insets on every window size change), applied as anchors margins
  on the panes and article area and as a margin on the dock's cell row.
- No new user-visible English text, so no `scripts/update-translations.ps1` run.
- Needs an on-device pass in both orientations before it is claimed verified.
