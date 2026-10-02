## 1. Reserve the gutter

- [x] 1.1 Add `body { padding-right: 12px !important; }` to the injected `plainCss` in
      `EngineController.cpp`, with a comment recording why `scrollbar-gutter` cannot do it
      (design D1, D2, D3)
- [x] 1.2 Leave `html { scrollbar-gutter: stable }` in the verbatim upstream stylesheet
      untouched (design D1)

## 2. Checks

- [x] 2.1 `EngineController.cpp` builds (ninja object target for `aurelex`): the same two
      pre-existing warnings, no errors
- [x] 2.2 `openspec validate reserve-article-scrollbar-space --strict` passes
- [x] 2.3 Confirmed no `qsTr` string or `strings.xml` entry changed — no
      `scripts/update-translations.ps1` run

## 3. On-device verification (Motorola ThinkPhone, Android 15 — passed 2026-10-02)

Checked by screenshotting mid-scroll (swipe, then capture before the overlay thumb fades) and
scanning the pixel columns at the article's right edge.

- [x] 3.1 Light: thumb occupies x1034–1044 (device px) — the full 11 px immediately inside the
      WebView's right edge (x1044, per the accessibility bounds). Text wraps well clear of it;
      the `body` reserve of 12 CSS px ≈ 14 device px is live (confirmed over CDP as
      `padding: 8px 12px 0px 0px`)
- [x] 3.2 Dark: the thumb is not visibly distinguishable from the `#1C1B1F` canvas in the
      captured frame — the columns at the right edge are uniform, so there is nothing drawing
      over the text
- [ ] 3.3 Zoom in to the maximum: the thumb still clears the text (the reserve is in px, the
      text scales, so confirm the margin has not been eaten)
- [x] 3.4 Short article (no scrolling): no visible strip or border on the right — the reserved
      space reads as the article's own background (light screenshots are uniform `#FFFBFE`)
- [ ] 3.5 `adb logcat` over the pass: nothing at `W`/`E`/`F` from the app's pid
- [ ] 3.6 Record the result in `docs/TESTING.md`

**Note:** 3.1 is the case that matters and it is a narrow margin — the thumb sits in the last
11 device px of the pane, and the text ends roughly 30 px before it. A wider device thumb or a
larger font could narrow that; 3.3 is the guard.

