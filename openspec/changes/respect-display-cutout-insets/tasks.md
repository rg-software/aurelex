## 1. Read the cutout on the Android side

- [ ] 1.1 In `AurelexActivity.java`, add a private helper that returns the
      `DisplayCutout`'s safe insets (`getSafeInsetLeft/Top/Right/Bottom`) from the
      decor view's `getRootWindowInsets()`, guarded by
      `Build.VERSION.SDK_INT >= 28` and returning 0 below (design D3)
- [ ] 1.2 Make `getSystemInsetTop()` / `getSystemInsetBottom()` return the **max**
      of the system-bar inset and the corresponding cutout safe inset, keeping the
      existing resource fallback for pre-28 and for a zero inset (design D1)
- [ ] 1.3 Add `getSystemInsetLeft()` / `getSystemInsetRight()` with the same shape
      and the same error handling (`Log.w` on failure, 0 as the answer) (design D2)

## 2. Forward the insets to QML

- [ ] 2.1 `EngineController.hpp`: declare `Q_INVOKABLE int systemInsetLeft() const;`
      and `systemInsetRight()` beside the existing pair, with a comment noting the
      values are the union of the system-bar and display-cutout insets
- [ ] 2.2 `EngineController.cpp`: implement both with the same
      `QJniObject::callStaticMethod<jint>` / `#if defined(Q_OS_ANDROID)` shape,
      returning 0 off Android

## 3. Apply the insets in QML

- [ ] 3.1 `app/main.qml`: `ApplicationWindow.color: root.uiBg`, so the inset strip
      at any edge is app background rather than the window's clear colour (design D4)
- [ ] 3.2 `_refreshInsets()`: read the two new values, divide by `_insetDpr`, and
      store them as `_insetLeft` / `_insetRight` (design D7)
- [ ] 3.3 Add `leftMargin: root._insetLeft; rightMargin: root._insetRight` to the
      shared anchor line of all five panes — `searchPane`, `dictsPane`,
      `groupsPane`, `favoritesPane`, `ftsPane` (design D4)
- [ ] 3.4 `navDock.navRow`: give the cell row the same left/right margins while
      `navDock` itself keeps its full-bleed background and height (design D5)
- [ ] 3.5 Update the comment on `_insetTop` / `_insetBottom` to say the values are
      unions with the display cutout and that the horizontal pair exists for the
      same reason

## 4. Guard against silent gaps

- [ ] 4.1 Grep every `top: topBar.bottom` pane and confirm each carries both
      margins, so a pane added later is caught in review (design Risks)
- [ ] 4.2 Confirm no `qsTr` string was added or changed; if one was, run
      `scripts/update-translations.ps1` and update `values-ru` / `values-ja` in the
      same change
- [ ] 4.3 `openspec validate respect-display-cutout-insets --strict` passes
- [ ] 4.4 `pwsh -File .\app\build.ps1 -Configuration Debug` + `adb install -r`, and
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

- [ ] 5.1 Portrait: the camera area is covered by the non-interactive top strip and
      `_insetTop` still equals the full cutout height (110 px) — the change must be
      a no-op here
- [ ] 5.2 Landscape (rotate from portrait, camera on the left): the article, the
      search field and the dock's outermost tab cell all start at or after
      `x = 110` in device px — i.e. no a11y node overlaps the cutout rect
- [ ] 5.3 Landscape the **other** way (`user_rotation 3`, camera on the right): the
      right-hand cells clear the cutout, and the left edge is *not* inset (proves
      the values are per-edge, not symmetric)
- [ ] 5.4 Cold start with the device already in landscape: the clearance is correct
      on the first frame, with no rotation event
- [ ] 5.5 Rotate back to portrait: no leftover horizontal inset (the side margins
      return to 0) and the top strip still covers the camera
- [ ] 5.6 No regression on the other panes: the Dictionaries, Groups, Favorites and
      Full-text search panes are inset identically and the catalog pane and group
      membership editor inherit it
- [ ] 5.7 IME regression guard: with an article open, focus the field — suggestions
      still appear and the article is not disturbed (the inset path must not fire on
      a height-only resize)
- [ ] 5.8 Both themes: check the inset strip at each edge in light and dark — it must
      be indistinguishable from the neighbouring background
- [ ] 5.9 `adb logcat` over the pass: no new warnings from the app's pid, no ANR

## 6. Documentation

- [ ] 6.1 `docs/TESTING.md`: add rows for "rotate with an article open on a cutout
      device" (including the right-edge rotation) so the symptom is searchable
- [ ] 6.2 Note in `docs/TESTING.md` that portrait is unchanged by design, so a
      future report of "the camera area looks different in portrait" is not a
      regression
