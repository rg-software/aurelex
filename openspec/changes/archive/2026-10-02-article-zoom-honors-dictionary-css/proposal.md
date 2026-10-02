## Why

Article zoom is implemented as a CSS **root font-size** on `<html>` (the injected
`zoomCtrl` in `EngineController::rewriteArticleUrls`, flipped live by `gdSetZoom`). That
scales text which *inherits* the root size. It cannot scale text whose size a dictionary's
own bundled stylesheet pins with an absolute unit — and `collinslaw` does exactly that.

Measured on device (Motorola ThinkPhone, Android 15), `law` in `collinslaw`, driving the
real controller and reading the live document over CDP:

| | zoom 100 | zoom 200 |
|---|---|---|
| `<html>` font-size | 16px | **32px** |
| `.gdarticlebody span` | 16px | **16px** |
| span rendered width | 346px | **346px** |

The zoom mechanism itself is correct — the root doubles. `collinslaw` ships a `.css` inside
its `.mdx` containing `span { font-size: 16px !important }` (plus `body`, `.s8`,
`.citou_head` in px), which out-specifies the root and pins the entry text. The article
therefore renders identically at every zoom level.

This is **not** a format difference. An `.mdx` with no bundled CSS (Black's Medical) and
the DSL fixtures both scale normally. It is a per-dictionary property of the author's
stylesheet, so it can appear in any format.

The shipped spec currently overstates the guarantee: "Article zoom reflows to the screen
width" says zooming enlarges the text, with no exception, and `docs/TESTING.md` §18c/§18g
are written as if zoom always scales. Left as-is, the correct `collinslaw` behaviour reads
as a regression each time someone tests it.

## What Changes

- **The zoom requirement states its real boundary.** Zoom scales text that inherits the
  article's root font size; element sizes a dictionary's bundled stylesheet sets in an
  absolute unit (px/pt) are not scaled, because those declarations override the root for
  their own content. The requirement stops promising "the text is enlarged" unconditionally
  and instead promises what the mechanism actually guarantees.
- **The limitation is recorded as deliberate, not a bug.** Reaching absolute-sized text
  needs an injected `!important` declaration of equal-or-higher specificity, which would
  override the dictionary's *intentional* typography (heading sizes, emphasis) as collateral
  — a worse outcome than the unscaled-by-zoom behaviour. The app does not fight dictionary
  CSS; see `design.md` D1.
- **The scope is stated precisely**, so the limitation is not mis-attributed to a format:
  it is per-dictionary, and the known trip case is `collinslaw` (`span { font-size: 16px
  !important }`). A dictionary with no bundled stylesheet, or one using relative units,
  scales normally.
- **`docs/TESTING.md`'s zoom expectations are corrected** to match, so the next person
  testing zoom on a CSS-heavy dictionary files it as the known limitation rather than a
  defect.

No implementation changes: the zoom mechanism is already correct. This change makes the
contract and the tests tell the truth about it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: "Article zoom reflows to the screen width" gains the boundary of what zoom can
  scale, and the reason the rest is left alone. The requirement keeps its reflow guarantee
  (enlarged content re-wraps, no horizontal scrolling) and its "one global zoom level"
  guarantee; it stops implying that every dictionary's content responds to zoom.

## Impact

- `openspec/specs/lookup/spec.md` — the zoom requirement's description and one scenario.
- `docs/TESTING.md` — the zoom table (§18c, §18g) gains the per-dictionary caveat and the
  `collinslaw` trip case; the observations become checkable rather than aspirational.
- No application code changes. No engine, carve, `gd_*` boundary, staging or catalog change.
- No user-visible English text changed, so no `scripts/update-translations.ps1` run.
- Verified by measuring the live document over CDP on a Motorola ThinkPhone (Android 15):
  root font-size 16px → 32px while `.gdarticlebody span` stays 16px at zoom 200.
