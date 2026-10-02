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
- [x] 3.3 Zoom in to the maximum: the thumb still clears the text (the reserve is in px, the
      text scales, so confirm the margin has not been eaten). **Done** on `The World Factbook
      2014` → `Zimbabwe` (a StarDict that *does* scale), zoomed to the 250% ceiling, scrolled,
      captured mid-scroll, and scanned the right-edge columns: the text's rightmost ink is at
      x≈995 and the thumb occupies x1034–1044, a ~39 px gap — the reserve holds at max zoom.
      `collinslaw` was also at the ceiling and its text is unchanged, which is the known
      absolute-size limitation, not this change
- [x] 3.4 Short article (no scrolling): no visible strip or border on the right — the reserved
      space reads as the article's own background (light screenshots are uniform `#FFFBFE`)
- [x] 3.5 `adb logcat` over the pass: nothing at `W`/`E`/`F` from the app's pid. **Done.**
      Cleared the buffer, scrolled the max-zoom article both ways, and found no app-pid line at
      `W`/`E`/`F`. (The only app-pid warnings on the device are the pre-existing `QML Dialog:
      Accessible must be attached to an Item` lines and an `[article-server] asset 404:
      "favicon.ico"`, both emitted at launch and unrelated to this pass.)
- [x] 3.6 Record the result in `docs/TESTING.md`. Added the "Article scrollbar clearance"
      subsection with rows 18t–18w (max-zoom clearance, 100% clearance, short-article
      invisibility, clean logcat).

**Note:** 3.1 is the case that matters and it is a narrow margin — the thumb sits in the last
11 device px of the pane, and the text ends roughly 30 px before it. A wider device thumb or a
larger font could narrow that; 3.3 is the guard.

