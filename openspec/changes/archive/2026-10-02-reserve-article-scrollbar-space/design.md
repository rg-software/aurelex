# reserve-article-scrollbar-space — design

## Context

- The article is shown in a `QtWebView`, which on Android is a platform view whose document
  Chromium renders. Android's WebView draws **overlay** scrollbars: the thumb is composited
  over the page and is not given layout space.
- This is a documented property of overlay scrollbars, not a WebView bug: per the CSS
  Scrollbars spec, `scrollbar-gutter` reserves space for *classic* scrollbars only, and has
  no effect on overlay scrollbars (`scrollbar-gutter: stable` is nevertheless present on
  `html` in the verbatim upstream `article-style.css`, so it is inert here).
- The app's injected `plainCss` (in `EngineController::rewriteArticleUrls`) neutralizes the
  "modern" style's bordered card:

  ```css
  .gdarticle { border: none !important; …; padding: 0 !important; … }
  ```

  The stylesheet's `.gdarticle` carries `padding-left: 2em; padding-right: 2em`. Zeroing it
  for the borderless look therefore also removed the only right-hand inset, which is what
  let the text reach the edge the thumb occupies.

## Goals / Non-Goals

**Goals:**
- Article text is not drawn under the floating scrollbar, at any zoom level the app offers.
- The reserve is not visible when there is no thumb (same color as the article background).

**Non-Goals:**
- Changing *which* scrollbar the platform draws, or replacing it with a custom one.
  The platform's overlay thumb is the intended affordance; the fault is only that it has no
  space.
- Touching the verbatim upstream stylesheet. The reserve is injected, like the other
  Android adjustments in `plainCss`.

## Decisions

**D1 — Reserve the gutter with `body { padding-right: 12px !important }`, not
`scrollbar-gutter`.**
`scrollbar-gutter: stable` cannot help (Context). A layout inset is the only lever that
works against an overlay scrollbar, and `padding-right` on an auto-width block reduces the
content width without overflowing.

- *Why not force a classic scrollbar instead*, by setting a width on `::-webkit-scrollbar`
  (which Chromium documents as turning an overlay scrollbar into a classic one): that
  replaces the platform's thumb with a custom-styled one on every device and in both themes
  — a larger, more opinionated visual change than reserving a strip the user asked for.
  Revisit only if the platform thumb ever proves not to clear the inset.

**D2 — The inset is on `body`, not on `.gdarticle`.**
`.gdarticle` is the per-entry wrapper, but the engine also emits content outside one (a
"not found" message, for instance). A `body`-level inset covers the whole document's
in-flow content. It leaves the fixed-position candidate overlay (`#gd-sugg`, which is
`left:0;right:0` relative to the viewport) alone, which is correct: that pane has its own
scrollbar but its rows carry their own padding.

**D3 — 12px, and it is the one number.**
Chosen to exceed the thumb's on-screen thickness with a few pixels of margin. If a device's
thumb is wider, this is the single value to raise; the on-device pass pins it.

## Ruled out

- **`scrollbar-gutter: stable` (again).** Already present upstream; no effect on overlay
  scrollbars. Removing it would churn a verbatim engine file for no behavior change.
- **Hiding the scrollbar** (`scrollbar-width: none` / `::-webkit-scrollbar { width: 0 }`).
  That removes the affordance rather than making room for it — the opposite of the request.
- **`WebView.setVerticalScrollbarOverlay(false)`.** The Android method is deprecated and
  documents "no effect" since API 23, and QtWebView does not expose the native `WebView` to
  QML or QML-adjacent C++ without a Java-side change.
- **Widening the app's own QML pane** instead of the document. The WebView is a platform
  view that fills the pane; the document is what has to inset its content.

## Risks / Trade-offs

- **[A fixed inset is present even when the article does not scroll.]** → It is painted the
  article's own background (already synced to the app's background), so it is not visible;
  the pinned scenario "The reserved space is not visible as a gap" covers this.
- **[12px may not be the device's thumb width.]** → Deliberately larger than the expected
  thumb; the on-device pass in `tasks.md` §3 confirms clearance and this is the knob.
