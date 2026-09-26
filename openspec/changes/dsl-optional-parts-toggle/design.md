## Context

See proposal.md - Why for the motivation. The mechanics that shape the approach:

The engine emits hidden-zone markup that Aurelex already reproduces faithfully:

- `engine/src/dict/dsl.cc:790` — `[*]…[/opt]` becomes `<span class="dsl_opt" id="O<id7>_<nom>_opt_<k>">`.
- `engine/src/dict/dsl.cc:1515-1527` — when the dictionary has hidden zones, one expander per entry:
  `<img src="qrc:///icons/expand_opt.svg" class="hidden_expand_opt" id="O…_expand" onclick="gdExpandOptPart('O…_expand','gd-<dictId>')" alt="[+]">`
- `engine/src/article_maker.cc:673` — each dictionary body is wrapped in `<section class="gdarticlebody" id="gd-<dictId>">`, so the second `gdExpandOptPart` argument resolves.
- `app/android/assets/stylesheets/article-style.css:548` — `.dsl_opt { display: none; }` (upstream default) and `:569` `.hidden_expand_opt` (16px wide, `cursor:pointer`).

What breaks it is entirely in our layer: `EngineController::rewriteArticleUrls` (`app/EngineController.cpp:1076-1080`) deletes the `<script src="…/gd-builtin.js">` element, and `engine/src/scripts/gd-builtin.js:61` is the only definition of `gdExpandOptPart`. `carve/gd_boundary.cc` pins `displayStyle = "modern"` and never sets `optPartsAutoExpand`, so the auto-expand style block at `engine/src/article_maker.cc:105-113` is not emitted either — collapsed-by-default is the state we want to keep.

Two constraints worth stating up front, because they decide the approach:

1. **`engine/` is off-limits.** Every deviation lives in the boundary. So the toggle must be implemented without touching `dsl.cc` or `gd-builtin.js`.
2. **The article page has no live C++/JS bridge.** `qrc:///` is rewritten to the loopback `ArticleServer` base, and Qt WebChannel is a no-op shim. Anything the article needs at runtime has to be either a bundled asset or injected HTML.

## Goals / Non-Goals

**Goals:**

- The upstream expander icon becomes a working show/hide control inside the inline article surface, with upstream's own semantics (alt `[+]`/`[-]` state flag, icon swap, toggling the hidden zones of that dictionary entry).
- The revealed content participates in normal article behavior (links, audio, resources).
- A touch-sized hit area for the control.
- Zero engine delta, zero new `patches/` entry, zero new `gd_*` boundary function.

**Non-Goals:**

- No user-facing setting for the default expanded/collapsed state (the spec pins collapsed-by-default, matching upstream).
- No new localization strings: the control is an icon, and the `alt` text stays the upstream `[+]`/`[-]`.
- Not reviving the rest of `gd-builtin.js` (article collapse/expand, `articleview.*` desktop bridge, iframe resizer, in-page search highlight via `mark.min.js`). Each is a separate feature with its own mobile interaction design.
- Not touching the `articleSizeLimit` auto-collapse path (`engine/src/article_maker.cc:554`); the boundary leaves that at -1, so it never fires.
- Not making `<ex>` example spans interactive — they are already always visible and correctly styled.

## Decisions

### D1. Ship a purpose-built article-controls script, not upstream's `gd-builtin.js`

Add `app/android/assets/scripts/gd-article-controls.js` defining `window.gdExpandOptPart`, and inject `<script src="<base>/scripts/gd-article-controls.js">` from the same block in `rewriteArticleUrls` that already injects `darkreader.js` (`app/EngineController.cpp:1154-1198`).

*Alternative — bundle `gd-builtin.js` verbatim and drop it from `stripScripts`.* Rejected: most of that file is the desktop bridge we deliberately removed. `gdAttachEventHandlers` attaches click handlers to every `.gdarticle` and routes taps of a dictionary-name header into `gdExpandArticle`, which calls `articleview.collapseInHtml(id, …)` **outside** a try/catch (`engine/src/scripts/gd-builtin.js:113,123`) — a `ReferenceError` on every header tap in the app, plus `gdCheckArticlesNumber` auto-expanding a collapsed single-dictionary article behind the user's back. `gdExpandOptPart` is the only self-contained piece, and it is ~15 lines.

*Alternative — re-implement the toggle from the QML click probe.* Rejected: the state lives in the WebView DOM, so the probe would have to reach in and mutate it anyway, fighting the existing `data-action`/`data-w` dispatch for a second, unrelated kind of tap.

### D2. The script must resolve icon URLs from the loopback base, not `qrc:///`

Upstream's handler assigns `d1.src = "qrc:///icons/collapse_opt.svg"`. Android's WebView cannot load `qrc:///`, so a verbatim copy of the function would expand the zone but leave a broken image — the exact failure the spec scenario "The control icon renders" forbids. The script therefore derives the origin from its own `document.currentScript.src` (drop the trailing `/scripts/<file>`) and builds `<origin>/icons/collapse_opt.svg` / `/icons/expand_opt.svg` from it. Both SVGs are already in the APK assets (`app/android/assets/icons/`) and `ArticleServer::classify` already serves `icons/*.svg` from `assets:/`, so only the *swapped* src needs this; the engine's original `qrc:///icons/expand_opt.svg` is already rewritten to the loopback base by `rewriteArticleUrls`.

*Alternative — inject the base as a global from C++.* Rejected as redundant: the script already knows its own URL, and deriving it keeps the asset self-contained (it keeps working if the port ever changes).

### D3. Keep upstream's toggle semantics verbatim, including the per-dictionary scope

`gdExpandOptPart` flips `alt` between `[+]` and `[-]`, swaps `src`, and sets `display: inline` / `none` on **every** `.dsl_opt` under the `gd-<dictId>` section named by the second argument. One expander is emitted per dictionary entry (`dsl.cc:1515`), so per-dictionary scope is the correct granularity and matches what a reader expects: revealing one entry's hidden notes does not reveal another's. Nested zones inside the toggled section follow the parent, which is also upstream's behavior.

### D4. Enlarge the hit area with an injected CSS override, not a stylesheet edit

The bundled `article-style.css:569` sizes the icon at `width: 16px` — desktop-pointer sized and below any reasonable touch target. The injected `<style>` block in `rewriteArticleUrls` (next to the existing `plainCss`, `app/EngineController.cpp:1140-1152`) adds an override that keeps the glyph visually 16px but grows the tappable box via padding and negative margin.

*Alternative — edit `app/android/assets/stylesheets/article-style.css`.* Rejected: those files are verbatim upstream copies; a local edit is an invisible divergence that an upstream bump would silently revert, and it would leak into the desktop stylesheet's other consumers. An injected override is already the established pattern here (dark mode, plain background) and is obviously ours.

### D5. No QML-side change; the existing click probe already cooperates

`app/main.qml:2502-2518` installs a capture-phase click listener that calls `preventDefault()` only for `[data-action]`/`[data-w]` matches and for `/gdau/`+`/gdlookup/` hrefs. The expander is an `<img>` with an inline `onclick`, no `data-*` attribute and no ancestor `<a>`, so the probe records an empty href, prevents nothing, and lets the inline handler run in the bubble phase. Nothing to change there — worth a regression check rather than a code change.

### D6. Turn off the engine's "always expand optional parts" preference

`Config::Preferences::alwaysExpandOptionalParts` defaults to `true` (`engine/src/config.cc:148`) and every `ArticleMaker` call passes it straight through (`engine/src/article_maker.cc:337,357,368`). With it on, `makeHtmlHeader` injects `.dsl_opt { display: inline }` + `.hidden_expand_opt { display: none }` (`engine/src/article_maker.cc:104-113`): the optional text renders expanded and the expander icon is hidden — the control is present in the markup, so a markup-only assertion passes, while on screen it is invisible and unreachable. The boundary sets it to `false` beside the existing `displayStyle` preference (`carve/gd_boundary.cc:357`), so `article-style.css`'s `.dsl_opt { display: none }` wins and the 16px expander stays visible for the injected handler to drive. The smoke assertion guards the override block's absence (`OPT_OVERRIDE`), not just the expander's presence.

*Alternative — strip the injected `<style>` block in `rewriteArticleUrls`.* Rejected: that block is a symptom, and the preference is the actual switch; string-stripping engine output is exactly what the `stripScripts`/dark-mode removals already do for cases with no configuration equivalent. This one has one.

## Risks / Trade-offs

- **Icon appearance under Dark Reader** → the article runs `DarkReader.enable()` (`app/EngineController.cpp:1188`), which can recolor the swapped-in SVG. Cosmetic at worst; verify the control stays legible in both themes and, if it does not, restrict the Dark Reader ignore list to the control rather than disabling it globally.
- **The reveal is not remembered across document re-renders** → a fresh lookup, or a back/forward navigation re-rendering the article from the cached `currentHtml` string, resets the state to collapsed. This is deliberate and pinned by the spec scenario "Re-rendering the article restores the collapsed state": it matches a fresh page load and avoids persisting UI state the app does not model. Note what does *not* reset it: the dark-mode toggle and the zoom controls are in-place `runJavaScript` calls against the live document (`app/main.qml:2476-2490`, via the injected `gdSetDarkMode` / `gdSetZoom` controllers), and `DarkReader` only adds and removes a stylesheet, so a revealed zone stays revealed across both. If losing the reveal on back-navigation proves annoying, the follow-up is QML-side state, not a change to this design.
- **Dictionaries that put real content in hidden zones** → they become readable, which is the point, but it can change how long an article looks at a glance. Not a correctness risk.
- **Touch-target override is a blunt CSS rule** → it applies to every `.hidden_expand_opt` in the article. That is exactly the set of controls we want resized; there is no other user of the class.
- **A `<script>` per article load** → one extra loopback request per render, same as the existing `darkreader.js` fetch, served from the local in-process server. Negligible.
