# article-zoom-honors-dictionary-css — design

## Context

Zoom is a **CSS root font-size** on the article document, not a page scale:

```css
html { font-size: N%; }                                     /* baked by rewriteArticleUrls */
document.documentElement.style.fontSize = p + '%';          /* live gdSetZoom(percent)   */
```

That design is deliberate and is what gives reflow instead of scaling a fixed-width column
(it is why there is no horizontal scrollbar at 250%, per the archived
`article-zoom-reflow` change). Its cost is that it only reaches text which resolves its size
**through the root** — inherited, `em`, `rem`, or the `medium` default. Text with an
absolute `font-size` does not consult the root at all.

A dictionary's own stylesheet is loaded into the same document. When it pins a size in px,
it wins for its own elements — and it wins twice over when it uses `!important`.

Measured (`law` in `collinslaw`, real `gdSetZoom` over CDP):

| | zoom 100 | zoom 200 |
|---|---|---|
| `<html>` font-size | 16px | 32px |
| `.gdarticlebody span` | 16px | 16px |
| span width | 346px | 346px |

`collinslaw`'s bundled CSS (`span`, `body`, `.s8`, `.citou_head`, two of them `!important`).

## Goals / Non-Goals

**Goals:**
- State the real, testable boundary of the zoom guarantee in the spec.
- Make it explicit that this is per-dictionary, so it is not filed against a format.
- Correct the test document so the correct behaviour is not treated as a regression.

**Non-Goals:**
- Making zoom scale dictionary-pinned absolute sizes. Deliberately declined — see D1.
- Changing the zoom *mechanism* (root font-size). It works as designed and is what makes
  reflow possible; the limitation is a property of the CSS cascade, not of this choice.
- Any per-dictionary zoom memory. The spec keeps zoom global.

## Decisions

**D1 — Do not fight a dictionary's absolute font sizes.**
The only way to scale them is an injected declaration that out-specifies the dictionary's
own — matching or exceeding its specificity *and* its `!important`, e.g.
`.gdarticlebody span { font-size: <scaled> !important }`.

Declined, for three reasons:

- *It would break the dictionary's intentional typography.* `collinslaw`'s px sizes are not
  an accident: they are how the dictionary distinguishes its heading (`.citou_head`, 19px)
  from body text (16px). Forcing everything onto one scaled root flattens that hierarchy —
  a worse reading experience than "zoom does not change this dictionary".
- *It requires guessing at unknown CSS.* There is no general way to rewrite an author's
  absolute sizes to relative ones at runtime without a CSS parser and an opinion about every
  unit (`px`, `pt`, `pc`, `in`, `cm`, `mm`). The app injects a handful of narrow, purposeful
  rules today; this would be a category change.
- *It contradicts an existing project principle.* The app already declines to rewrite
  dictionary content it does not own (it overrides only its own chrome — the card frame, the
  toolbar clearance, the scrollbar gutter). Patching dictionary typography is the same class
  of intervention, with a worse failure mode.

**D2 — Record it as a spec boundary, not a bug.**
The requirement currently promises the text is enlarged with no exception. That promise is
false for any dictionary that pins absolute sizes, and a spec that overstates its guarantee
is a spec nobody can test honestly. The requirement is reworded to promise what the
mechanism actually does, plus a scenario for the pinned-size case so the behaviour is
asserted rather than tolerated.

**D3 — State it as per-dictionary, with the trip case named.**
The tempting one-line summary ("zoom doesn't work for mdx") is wrong and would send the next
person down a format-based investigation. The change names `collinslaw` and the exact
declaration, and a scenario asserts the converse (same format, no absolute sizes → scales),
so the claim stays falsifiable.

## Ruled out

- **`transform: scale()` or a page zoom instead of a font-size.** It would scale everything
  uniformly, including the pinned text, but it scales the *layout* too: text stops re-wrapping
  and a horizontal scrollbar appears, which is exactly what `article-zoom-reflow` was written
  to eliminate.
- **Per-dictionary zoom.** Would not help: the pinned text ignores the root at every value.
- **Detecting "this dictionary pins sizes" and disabling the zoom controls.** The rest of the
  article surface (headings outside the pinned selector, images) still scales, and the
  controls are global and shared; disabling them per-dictionary contradicts the spec's single
  global level and would be a worse experience than a partial scale.

## Risks / Trade-offs

- **[Zoom on `collinslaw` now visibly does nothing to the entry text.]** → Accepted and
  documented. The alternative (D1) trades a missing feature for broken typography in that
  dictionary, which is the worse trade.
- **[A future dictionary with absolute sizes gets the same treatment.]** → Expected, and the
  reason the spec names the mechanism rather than the dictionary. The named case is an
  example, not an allow-list.
- **[Not verified for every absolute unit.]** → The measurement covers `px`, which is what
  the fixtures use and by far the common case; `pt` and the other absolute units behave
  identically by definition (they do not resolve through the root). No fixture exercises them,
  and this change adds none.
