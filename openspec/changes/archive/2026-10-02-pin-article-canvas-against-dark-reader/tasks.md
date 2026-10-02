## 1. Make the article canvas the app's background

- [x] 1.1 `EngineController.cpp` holds the pair as `canvasBgLight` / `canvasBgDark`
      (`#fffbfe` / `#1c1b1f`), selected by `m_darkMode` (design D1)
- [x] 1.2 `plainCss`'s `html, body` background is baked per render (`%1` = the current
      mode's value) so the first painted frame is correct in both themes, with no flash of
      white on a dark cold load (design D2)
- [x] 1.3 The controller asserts the canvas as an **inline `!important` declaration** on
      both `html` and `body`. A stylesheet rule alone does not survive dark mode: Dark
      Reader overrides html/body's background from inside a cascade `@layer`, and a layered
      `!important` outranks an unlayered one, which is why the article rendered
      `#242525`/`#222323` instead of `#1c1b1f` (design D3 — found on device, see §4)
- [x] 1.4 `gdSetDarkMode` re-asserts the canvas on a live flip, before its early-return
      guard, so an already-dark article still picks up the current value
- [x] 1.5 The controller is injected into `<head>`, where `document.body` does not exist yet,
      so it re-asserts once on `DOMContentLoaded` (or immediately if already parsed)

## 2. QML keeps the same pair

- [x] 2.1 `root.uiBgHex()` returns the two values for the current mode — a plain
      two-value function, not a formatter (design D1)
- [x] 2.2 `uiBlankHtml()` themes the blank base document on its `<html>` element; all five
      `loadHtml("<html><body></body></html>")` call sites go through it, so the native
      WebView's white canvas is never visible in dark mode
- [x] 2.3 `_applyArticleDarkMode` restates the blank document's inline `background` on a
      theme flip and then calls `gdSetDarkMode` for the article
- [x] 2.4 The candidate pane takes its background from `uiBgHex()`, and
      `_applySuggestOverlay` stops writing `document.body.style.background` /
      `documentElement.style.background` inline — those writes were never removed by
      `_clearOverlayDom`, so they outlived the overlay and could strand the document on the
      previous theme's color (design D4)

## 3. Checks

- [x] 3.1 `qmllint` over `app/main.qml`: 234 diagnostics against a 246 baseline — fewer,
      with no new warnings and no errors (the drop is the deleted formatter's diagnostics)
- [x] 3.2 `EngineController.cpp` builds (ninja object target for `aurelex`): the same two
      pre-existing warnings, no errors
- [x] 3.3 Confirmed `QQuickWebView` has no `backgroundColor` property in Qt 6.6.3
      (`qml/QtWebView/plugins.qmltypes`), so no native-surface call site was overlooked
- [x] 3.4 Confirmed no `qsTr` string or `strings.xml` entry changed — no
      `scripts/update-translations.ps1` run, no `values-ru`/`values-ja` edit
- [x] 3.5 `openspec validate sync-article-background-with-theme --strict` passes

## 4. On-device verification (Motorola ThinkPhone, Android 15 — passed 2026-10-02)

Checked by pixel-sampling the article canvas against the QML pane in the same screenshot
(exact match required), and by querying the live document over CDP
(`chrome://inspect` endpoint on the WebView's `webview_devtools_remote` socket).

- [x] 4.1 Light, article open: canvas `#FFFBFE`, pane `#FFFBFE`, toolbar `#FFFBFE` — exact
- [x] 4.2 Dark, article open (cold, then flipped): canvas `#1C1B1F`, pane `#1C1B1F` — exact.
      CDP: `htmlBg = bodyBg = rgb(28,27,31)`, `getComputedStyle` confirmed, with
      `DarkReader.isEnabled() === true` (Dark Reader still transforms the text)
- [x] 4.3 Candidate pane (history / empty field): `#1C1B1F` in dark, `#FFFBFE` in light
- [x] 4.4 Headword suggestions dropdown: `#FFFBFE` in light, matching the pane
- [x] 4.5 Live theme toggle with an article open: canvas follows both ways
      (`rgb(28,27,31)` → `rgb(255,251,254)`), no leftover from the previous theme
- [x] 4.6 Live theme toggle with the candidate pane up: follows (this is the case the
      removed inline document write would have stranded)
- [x] 4.7 Blank base document: no white flash on a dark cold launch (top strip `#1C1B1F`
      sampled immediately after launch)
- [ ] 4.8 Article legibility in dark mode against `#1c1b1f` — Dark Reader's text still
      renders `#e5e0d8` on the new canvas; looked correct in the screenshots, but a
      deliberate typography read-through is still owed
- [ ] 4.9 `adb logcat` over the pass: nothing at `W`/`E`/`F` from the app's pid
- [ ] 4.10 Record the result in `docs/TESTING.md`

**Note for 4.2:** the stylesheet-only version of this change *looked* correct in the
light theme and failed in the dark theme — this is only visible on device, so the
light-theme-only check would have shipped the bug.

