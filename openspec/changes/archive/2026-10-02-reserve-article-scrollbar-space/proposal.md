## Why

On Android the article WebView uses **overlay scrollbars** — the thumb is painted *on top
of* the page, not in a gutter beside it. The app's injected article CSS also neutralizes the
"modern" style's bordered card (`.gdarticle { padding: 0 !important }`), which was where the
stylesheet's own `padding-right: 2em` lived. The two together mean article text runs to the
right-hand edge of the pane, and the floating thumb is drawn over the text while the reader
scrolls.

The upstream stylesheet already asks for `scrollbar-gutter: stable` on `html`, but that
property only reserves space for **classic** scrollbars; by specification it has no effect
on overlay scrollbars, so it is inert here.

## What Changes

- **The article document reserves a right-hand gutter** with `body { padding-right: 12px
  !important }` in the injected CSS (`EngineController.cpp`). The gutter is painted with the
  article's own background — already the app's background — so it is invisible except while
  the thumb is drawn, and the text never sits under the thumb.
- The reserve is on `body`, not `.gdarticle`, so it also covers content the engine emits
  outside a dictionary entry (for example a "not found" message).
- **Not changed:** the upstream `scrollbar-gutter: stable` on `html`. It stays; it is
  harmless where it is inert and takes effect if a future WebView uses classic scrollbars.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: the "Article rendering" requirement gains the guarantee that the scrolling
  affordance does not obscure the article's text. It states the user-visible contract (the
  floating scrollbar and the text do not overlap) without naming the CSS property, which is
  the implementation.

## Impact

- `app/EngineController.cpp` only: one declaration in the injected `plainCss`.
- No engine, carve, or `gd_*` boundary change; no signature change; no QML change.
- No user-visible English text changed, so no `scripts/update-translations.ps1` run.
- The exact reserve width is a visual judgement, first confirmed on a Motorola ThinkPhone
  (Android 15): the thumb occupies the last 11 device px of the pane and the text ends well
  clear of it (`tasks.md` §3). The maximum-zoom case is still owed.
