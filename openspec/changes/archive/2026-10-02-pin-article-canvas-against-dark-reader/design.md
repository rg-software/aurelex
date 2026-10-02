# sync-article-background-with-theme — design

## Context

See `proposal.md` — Why for the symptom. The shape of the problem:

- The Search tab's article area holds a `QtWebView`, which on Android is a **platform
  view**: a real child of the activity's view hierarchy, composited above the Qt scene.
  It ignores QML `z` and `clip`. So the QML pane behind it (`searchArticleArea`,
  `color: root.uiBg`) is *not* what the user sees in the article region — the WebView's
  own canvas is. Anything that wants the article to sit on the app's background has to
  paint the document.
- The app's background is Qt Quick Controls' Material `background`, aliased once in QML
  as `root.uiBg`. Its two concrete values (`#fffbfe` light, `#1c1b1f` dark) are pinned by
  the Qt 6.6.3 kit and are already restated a third time in
  `app/android/res/values{,-night}/colors.xml` for the starting window.
- Three documents live in that one surface over the app's life: the rendered **article**,
  the **blank base document** (loaded when there is no article, so `runJavaScript` has a
  document to talk to), and the **candidate pane** (an HTML `<div id="gd-sugg">` drawn
  *into* the current document). All three need the same background.

### What the CSS has to beat

`article-style-st-modern.css` (the style the carve forces, so the dark-mode stylesheet
variant is eligible) opens with `html { background-color: white } body { background: white }`.
The app therefore overrides with `!important` — that part was already right. The wrong part
was *what* it overrode it with.

## Goals / Non-Goals

**Goals:**
- The article surface's background is the app's background, in both themes, on the first
  painted frame and after a live theme flip.
- The blank base document and the candidate pane match it too.
- The change is as small as the problem: the pair of colors is corrected in the two
  places that already held it, not re-plumbed into a new single source of truth.

**Non-Goals:**
- Any change to the engine, the carve, or the `gd_*` boundary. The article CSS is injected
  by the app; nothing here belongs in `engine/` or `patches/`.
- Recoloring the native WebView *surface* (Android's `View` background, visible during
  overscroll). `QQuickWebView` in Qt 6.6.3 exposes no `backgroundColor` property at all —
  confirmed against `qml/QtWebView/plugins.qmltypes` — so it would take a JNI call into
  `AurelexActivity`. Out of scope; see Ruled out.
- Changing the article's *typographic* dark palette. Dark Reader still does that work; this
  change only fixes the canvas it sits on.

## Decisions

**D1 — Keep the color as a literal pair; do not resolve it from QML.**
`EngineController.cpp` holds `canvasBgLight` / `canvasBgDark` and selects by `m_darkMode`;
`main.qml` holds the same pair once, as `root.uiBgHex()`.

- *Why:* the observable requirement is two correct numbers. Deriving the value from
  `Material.background` at run time is architecturally tidier but costs a hand-rolled hex
  formatter (Qt 6's QML `Qt` singleton has neither `colorToString` nor an equivalent —
  verified against `qml/QtQml/Base/plugins.qmltypes`; `qmllint` flags the call) plus a new
  parameter on the `Q_INVOKABLE` `rewriteArticleUrls`. That was written, reviewed as
  disproportionate, and reverted. The pair is pinned by the Qt version carried in the kit
  and is not a value users or dictionaries can move.
- *Cost, accepted:* a future Qt upgrade that moves the Material palette leaves the article
  behind, exactly as it did before — but that drift is now the *only* remaining defect and
  is marked by a cross-reference comment in both files.

**D2 — The first frame is painted by a baked sheet rule; the live canvas is an inline
`!important` declaration.**
`plainCss` bakes the current mode's color into `html, body { background: %1 !important }`, and
the injected controller asserts the same value as an **inline `!important`** declaration on
both `html` and `body`.

- *Why two mechanisms:* they cover different windows. The sheet rule paints the first frame
  before any script runs (the controller's own initial call is a no-op — the mode is already
  baked into `__gdDarkMode`, so its guard returns immediately), and it is baked per render so
  a dark cold load never flashes the light value. The inline declaration is what actually
  holds once dark mode is on, for a reason that only showed up on device — see D3.
- *Why `body` too:* once `html` has a background, `body`'s no longer propagates to the
  canvas, so both must be set.

**D3 — Dark Reader outranks a stylesheet rule, so the canvas is asserted inline.**
Dark Reader injects `html { background-color: var(--darkreader-background-ffffff, #242525)
!important }` (and the `html, body` pair) from inside an anonymous cascade `@layer`. For
`!important` declarations a **layered rule beats an unlayered one**, and among layered rules
the **first layer wins** — so both a plain `!important` sheet rule and a same-`!important`
rule wrapped in a later `@layer` lose, no matter the specificity of the selector. Dark Reader
also inserts its styles at the *top* of `<head>`, so it wins the layer order too.

- *Why an inline declaration wins:* inline styles are not in any layer, and for `!important`
  the layering order puts the unlayered "user agent / author normal" tiers below layered
  author important — verified on device: `getComputedStyle(document.body).backgroundColor`
  went from `rgb(34,35,35)` to `rgb(28,27,31)` only after the inline `!important` was set.
- *Why not fight it with `darkSchemeBackgroundColor`:* that would mean configuring a
  vendored third-party script's palette, coupling the app's background to its heuristics.
  Asserting the canvas after it runs is direct and survives a Dark Reader upgrade.
- *Consequence for `--gd-bg`:* the custom property is gone. It existed to let one stylesheet
  rule be updated by one property write; the value is now written to two elements directly.

**D4 — The controller re-asserts on `DOMContentLoaded`.**
The injected controller is placed in `<head>`, where `document.body` does not exist yet, so
its first call can only reach `<html>`. It re-runs `gdAssertCanvas()` when the document has
parsed — which also lets Dark Reader's late style injection settle first. `gdSetDarkMode`
sets the canvas *before* its early-return guard, so a theme flip that lands on an
already-dark document still picks up the current value.

**D5 — The candidate overlay stops writing the document's background.**
`_applySuggestOverlay` used to set `document.body.style.background` and
`document.documentElement.style.background` inline. Those writes are removed.

- *Why they are safe to remove:* both possible host documents paint themselves — the article
  via the controller's inline assertion and the baked sheet rule, the blank document via
  `uiBlankHtml()` — and the flip restates the latter. The `<div id="gd-sugg">` keeps its own
  opaque `background`, which is what the panel actually needs.
- *Why leaving them would be actively wrong:* `_clearOverlayDom` only removed the `<div>`,
  never those inline writes, so once the overlay had drawn on the blank document the document
  kept that color for the rest of its life — a live theme flip would leave the pane on the
  old theme's background.

## Ruled out

Recorded so the next person does not re-derive them.

- **"Set the WebView's background with `setBackgroundColor`."** That is the Qt **WebEngine**
  API (`QWebEnginePage::setBackgroundColor`, used by the desktop `articleview.cc`). This
  app is **QtWebView** — `QtWebView::initialize()` in `main.cpp`, `Qt6::WebView` in
  `CMakeLists.txt` — and `QQuickWebView` has no such property. There is no call site to
  add; the desktop carve does not compile `src/ui/` at all.
- **Reaching the Android `WebView` through JNI to set its native background.** It would
  only affect what shows during overscroll and the pre-first-paint frame, both of which the
  document's own background already covers once D2 and D4 are in. Not worth a Java-side
  change and a lifecycle question (the view is re-created on tab switches).
- **Resolving the color from QML (`uiBgCss()` + a `surfaceBg` parameter).** Written, then
  reverted — see D1. It removed the duplication at the cost of a formatter and a signature
  change that outweighed the two numbers it replaced.
- **Telling Dark Reader to leave the canvas alone.** Concretely: setting its
  `darkSchemeBackgroundColor` to the app background, or adding the elements to its ignore
  list. Both couple the fix to a vendored third-party script's heuristics and break on its
  next upgrade; asserting the canvas after it runs (D3) needs neither. Leaving it unhandled
  is not an option — it demonstrably wins the cascade otherwise.
- **Setting `Material.backgroundColor` explicitly on the root.** The kit's
  `ApplicationWindow` already binds `color: Material.backgroundColor`, and `root.uiBg`
  aliases the same value; adding another binding would create two bindings to fight. The
  problem was never the app's own color — it was the article's.

## Risks / Trade-offs

- **[The pair is restated in C++ and QML, and can drift on a Qt upgrade.]** → Accepted
  deliberately (D1). The comment on each pair names the other file and `colors.xml`.
- **[The canvas is asserted from JavaScript, so it is re-applied per document load.]** → The
  alternative is losing to Dark Reader's layered `!important` (D3), which only became
  visible on device. The assertion is two `style.setProperty` calls per load and one per
  theme flip.
- **[Dark Reader could still recolor text that sits on the canvas.]** → Intended — that is
  its job. Only the canvas is pinned; the article's typographic dark palette is unchanged.
- **[The article's dark palette is now a darker, more purple-tinted surface than the
  `#242526` it replaces.]** → Intended: `#242526` is not one of the app's colors, which is
  the point. Verified on device: with the canvas pinned, Dark Reader's text still renders
  `#e5e0d8` and the page reads correctly (`tasks.md` §4).
- **[Unverified without hardware]** → Resolved for the seam itself: `tasks.md` §4 passed on
  a Motorola ThinkPhone (Android 15) in both themes, on cold load and on a live flip, with
  the empty-field history pane and the suggestions dropdown checked as well.
