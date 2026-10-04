## Context

See `proposal.md` — Why for the measurements. What shapes the approach:

- The article document is assembled in `EngineController::rewriteArticleUrls`
  (`app/EngineController.cpp`), which injects a `<style>` block containing the
  app's own article styling, and separately injects the dark-mode controller that
  appends `.gdarticlebody img{background:white !important;}` and calls
  `DarkReader.enable({brightness:100,contrast:90,sepia:10})`.
- That dark-mode style element is appended **later** than the main injected block,
  at toggle time, which is why the existing `gd_tag_*` override needs both the
  `.gdarticlebody` prefix and `!important` to win. The file says so in a comment
  at the override.
- The affected images are the app's own: `img.hidden_expand_opt`
  (`expand_opt.svg` / `collapse_opt.svg`, padded 12px and pulled up 12px by
  `margin: -12px !important` to enlarge the tap target) and the engine's
  pronunciation button `img[src*="playsound"]`, which sits inside an `<a>` and
  carries no class.
- DarkReader rewrites declared colours rather than leaving them alone, and
  publishes its result as a `--darkreader-*` custom property. Any explicit colour
  we write into the article is therefore a candidate for rewriting.
- The article document is inspectable without rebuilding the app: the WebView
  exposes a DevTools socket (`webview_devtools_remote_<pid>`), reachable with
  `adb forward` + the CDP HTTP/WebSocket endpoints. Every measurement in the
  proposal was taken that way.

## Goals / Non-Goals

**Goals:**

- No opaque box behind any of the app's inline control glyphs, in either theme.
- The headword is fully legible in dark mode on an article with hidden content.
- Content images keep the light plate.
- The fix lives beside the override it must out-specify, in the file that already
  documents this exact hazard.

**Non-Goals:**

- Removing the dark-mode white plate, or reconfiguring DarkReader.
- Changing the expander's geometry (the 12px padding / negative margin is a
  deliberate tap-target enlargement).
- Restyling dictionary-emitted icons, which are already correct.

## Decisions

**D1 — Force `background: transparent !important` on the control glyphs.**

The light-mode computed value is *already* `rgba(0, 0, 0, 0)`, so transparent is
the state the app is visually correct in today; making it explicit for dark mode
brings dark to parity rather than inventing a new colour.

The obvious alternative — set the background to the dark canvas colour so the box
blends — was rejected: DarkReader transforms declared colours, so a themed value
would be rewritten a second time and land somewhere else again. Transparent has
nothing to transform, which makes it the only value that is stable under
DarkReader.

*Alternative considered:* stop injecting `.gdarticlebody img{background:white}`
altogether. Rejected: it is load-bearing for content images, whose artwork assumes
a white page, and removing it would regress every dictionary with illustrations.

**D2 — Select the glyphs by the same idioms already used for `gd_tag_*`.**

```css
.gdarticlebody img.hidden_expand_opt,
.gdarticlebody img.gdcollapseicon,
.gdarticlebody img[src*="playsound"] { background: transparent !important; }
```

The `.gdarticlebody` prefix plus `!important` is required, not decorative: the
dark-mode controller appends its rule later with equal specificity. `playsound` is
selected by filename because that image carries no class — the same technique the
existing `gd_tag_` rule uses. `gdcollapseicon` is included because it is the
engine's own collapse-control class and is currently 0×0 in the articles checked;
including it prevents the same defect appearing when that control does render.

The rule is added as its own block rather than merged into the `gd_tag_*` rule,
because that rule also pins width, height and vertical-alignment, which are
meaningless for these glyphs.

**D3 — Verify by computed style, and by screenshot, in both themes.**

Computed-style assertions are the regression guard: "the control's background is
transparent" is exactly the property that regressed, and it is checkable without a
human comparing pixels. The screenshot is the acceptance check, because the user-
visible harm is a headword being partly hidden, which no computed value states
directly. Both are scripted in `tasks.md`.

**D4 — Check the remaining engine glyphs rather than assuming.**

`assets/icons/` also contains `lsasound.png`, `zipsound.svg`, `text2speech.svg`
and `folder-sound.svg`, none of which appeared in the articles inspected. The
tasks enumerate them as a check instead of adding speculative selectors now: a
selector with no observed defect is a liability, and the same rule can be widened
later with evidence.

## Risks / Trade-offs

- **A selector misses a glyph.** → The verification task enumerates the engine's
  inline glyph files and reports each one's computed background, so a miss shows
  up as a failing row rather than as a visual nit nobody notices.
- **The `!important` plate is load-bearing for content images.** → A scenario
  asserts the plate survives, and the rule is scoped to control glyph classes, not
  to `img` generally.
- **Specificity fragility if the dark-mode controller changes.** → Mitigated by
  the existing comment at the override site, which this change extends rather
  than supersedes; a future change to the controller's injection point should
  revisit both rules together.
- **Verified against one engine's articles.** → The guarantee is written against
  the app's own controls, which are engine-independent, but device verification
  should still cover at least one dictionary with an optional zone and one
  without.