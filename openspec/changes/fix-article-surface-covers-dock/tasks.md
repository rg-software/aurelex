## 1. Fix the layout overflow

- [x] 1.1 In `app/main.qml`, `searchArticleArea`: `Layout.minimumHeight` 300 → 88
      (design D1)
- [x] 1.2 Record the measured geometry and the "re-measure before raising it"
      warning in the comment at that declaration

## 2. Remove the orientation teardown

- [x] 2.1 Delete `_geometryInvalid`, `_lastGeoW`, `_lastGeoH` and the
      `prevLandscape !== nowLandscape` branch in `_refreshInsets` (design D2)
- [x] 2.2 Delete `!root._geometryInvalid` from `searchArticleLoader.active`
- [x] 2.3 Confirm nothing else referenced the deleted properties
      (`_pickerOpen` and `inlineWebReady` are untouched and unrelated)
- [x] 2.4 Keep `_refreshInsets`'s inset re-read and the `_pickerOpen` teardown
      (design D3)

## 3. Re-check the assumptions the fix rests on

- [x] 3.1 Confirm the overflow, not native staleness, is the cause: with the
      layout corrected *and* the teardown disabled, the dock paints (measured —
      see §4.1). Recorded in `design.md` § Ruled out
- [x] 3.2 Confirm no `qsTr` string was added or changed, so no
      `scripts/update-translations.ps1` run and no `values-ru`/`values-ja` edit
- [x] 3.3 `openspec validate fix-article-surface-covers-dock --strict` passes

## 4. Build

- [x] 4.1 `pwsh -File .\app\build.ps1 -Configuration Debug` + `adb install -r`;
      QML compiles with no new warnings

## 5. On-device verification (the fix is not claimed until this passes)

Device: Motorola ThinkPhone, Android 15, 1080×2400. Debug build on hardware.
Measurement method (no image reading available): magenta-accent pixel count in
the dock band — "is the dock band painting the accent, or the article?"
(reference: portrait dock visible **470**, landscape with the bug **15**, ~<50
means the dock is not painting) — plus `uiautomator dump` bounds for the real
overlap comparison, plus a dock-tab tap to prove hit-testing.

- [x] 5.1 Search tab, article open → rotate to landscape: **594** accent px;
      article bounds `[33,449][2365,822]`, article bottom **822** vs dock top
      **856** → no overlap. Tapping the Dicts tab in landscape navigated, so the
      dock is tappable, not just painted
- [x] 5.2 Same rotation, back to portrait: **470** accent px, same article still
      open
- [x] 5.3 Force-stop with the device already in landscape, relaunch, open an
      article: **594** accent px; article bottom **821** < dock top **856**
- [x] 5.4 Rotate twice in a row without touching anything: **594** accent px, no
      crash, article survives (there is no longer a teardown to flicker)
- [x] 5.5 IME regression guard: keyboard shown (`mInputShown=true`), typed
      `smok`, suggestions appeared in the WebView's own accessibility subtree
      (`desc='Smoking'`, `desc='Smoke Inhalation'`) — no regression
- [x] 5.6 Rotate on two non-article tabs: Dicts **669** portrait / **600**
      landscape; Full-text search **533** portrait / **600** landscape
- [x] 5.7 `adb logcat` over the pass: nothing at `W`/`E`/`F` from the app's pid,
      and no `ANR in` / `FATAL EXCEPTION` / `Fatal signal` anywhere in the buffer

## 6. Documentation

- [x] 6.1 `docs/TESTING.md`: rows for rotate-with-article-open, cold start in
      landscape, rotate twice, the non-article-tab rotation, and the IME guard
- [x] 6.2 The scroll-position reset on rotation is **measured, not assumed**, and
      recorded as pre-existing: `searchArticleView.onHeightChanged` restarts
      `articleReloader` when the height differs from `loadedAtHeight`, and
      `loadHtml` resets the scroll (scrolled → rotate there and back is
      pixel-identical to the unscrolled state: 0 % vs 9.5 % for top↔scrolled).
      `docs/TESTING.md` records it as the responsive-reflow path so it is not
      re-attributed to this fix
- [x] 6.3 The ruled-out hypotheses (stale native surface, `visible` toggle,
      the settled-width reconciliation that was built and discarded) are recorded
      in `design.md` § Ruled out
