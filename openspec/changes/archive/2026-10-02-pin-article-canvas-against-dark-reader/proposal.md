## Why

The article surface does not share the app's background color. In both themes it is
painted a shade of its own, and the seam is visible where the article meets the chrome:

| Theme | App background (`Material.background`, `root.uiBg`) | Article canvas |
|---|---|---|
| light | `#FFFBFE` | `#ffffff` |
| dark | `#1C1B1F` | `#242526` |

Light is a subtle difference (the app's background is very slightly warm) and reads as
a faintly dirty pane. Dark is plainly visible: `#242526` is lighter and greyer than
`#1C1B1F`, so the Search tab reads as a raised grey panel inside a near-black app. The
wrong pair was hardcoded in `EngineController.cpp` (the injected article CSS) and again
in `main.qml` (the candidate pane); both are corrected here.

Two further surfaces in the same pane carried the same class of fault:

- The **blank base document** the WebView loads when there is no article
  (`"<html><body></body></html>"`) has no background at all, so the native WebView's own
  white canvas shows through. In dark mode that is a white flash on every return to the
  Search tab, and a white pane whenever the candidate list is empty.
- The **candidate pane** (headword suggestions / recent lookups) painted itself from a
  third copy of the pair, and `_applySuggestOverlay` wrote `background` **inline** onto
  `document.body` and `document.documentElement`. `_clearOverlayDom` only removed the
  overlay `<div>` — never those writes — so the document was left holding the color the
  theme had when the overlay was drawn, and a theme flip could strand it on the previous
  theme's background.

## What Changes

- **The article canvas is corrected to `#fffbfe` / `#1c1b1f`.** `EngineController.cpp` holds
  the pair as two named constants and bakes the current mode's value into the article CSS so
  the very first painted frame is correct. Because Dark Reader overrides the document's
  background from inside a cascade layer — and a layered `!important` beats an unlayered one
  — the live canvas is held by an inline `!important` declaration the injected controller
  sets on `html` and `body` (found on device; see `design.md` D3). `gdSetDarkMode` re-asserts
  it on a live theme change, so the open article's canvas follows without a reload.
  `rewriteArticleUrls`'s zero-arg signature is unchanged.
- **QML keeps the same pair in one place**, `root.uiBgHex()`, read by the candidate pane
  and by the blank base documents. It is a plain two-value function.
- **The blank base documents are themed**, via a `uiBlankHtml()` helper, so the native
  WebView's white canvas is never visible.
- **The candidate pane uses `root.uiBgHex()`**, and no longer writes the document's
  background inline. That write is now both redundant (both documents paint themselves)
  and a staleness trap, so it is removed rather than kept in sync.

**Accepted trade-off:** the pair is stated twice — once in `EngineController.cpp`, once
in `main.qml` — so a Qt upgrade that moves `Material.background` will not move the
article with it. A cross-reference comment in both places is the only guard. Resolving
the color from QML instead was written and then deliberately dropped: it cost a
hand-rolled hex formatter (Qt 6's QML `Qt` singleton has no `colorToString`) and a new
parameter on `rewriteArticleUrls` to save two numbers that are pinned by the Qt version
and already restated in `colors.xml`. See `design.md` D1.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `usability-utilities`: "The resolved theme drives all app appearance" gains the
  guarantee that the article surface's background is the same color as the app's, in
  both themes, including the candidate pane that stands in for an article. It states the
  user-visible contract (no seam between the two) without naming the CSS custom property
  or the Material palette, which are the implementation.

## Impact

- `app/EngineController.cpp`: the article canvas pair, the baked first-frame rule, and the
  controller's inline canvas assertion.
- `app/main.qml`: a `uiBgHex()` helper and a `uiBlankHtml()` helper, five blank-document
  call sites, and the candidate overlay's colors and removed inline document write.
- No engine, carve, or `gd_*` boundary change — the boundary is untouched and this is
  app-side only. No signature change: `rewriteArticleUrls` stays zero-arg.
- No user-visible English text changed, so no `scripts/update-translations.ps1` run and no
  `values-ru`/`values-ja` edit.
- Verified on a Motorola ThinkPhone (Android 15) by pixel-sampling the canvas against the
  app background in both themes, on cold load and on a live flip — `tasks.md` §4. Also
  `qmllint` (no new diagnostics versus baseline), a build of `EngineController.cpp`, and
  `openspec validate --strict`.
