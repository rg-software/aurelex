## Why

In dark mode the article's own control icons are drawn on an opaque box that does
not match the article canvas, and for the hidden-content control that box is
positioned over the headword and hides its last characters.

Measured on device (ThinkPhone, Android 15, dark theme, `зоолог` from the
Russian catalogue dictionary), with the computed values read from the live
article document over the WebView's DevTools socket:

| | light | dark |
|---|---|---|
| `img.hidden_expand_opt` background | `rgba(0, 0, 0, 0)` | `rgb(36, 37, 37)` |
| `img[src=playsound]` background | `rgba(0, 0, 0, 0)` | `rgb(36, 37, 37)` |
| article canvas | `#FFFBFE` | `#1C1B1F` |

The cause is two rules, both reported by the CSS domain as matching
`.gdarticlebody img`:

1. the dark-mode controller injects `.gdarticlebody img{background:white !important}`
   (`app/EngineController.cpp`), a deliberate light plate so dictionary images
   that assume a white page look right;
2. DarkReader then rewrites that white, keeping `!important`, as
   `background-color: var(--darkreader-background-ffffff, #242525) !important`.

`#242525` is DarkReader's transform of white and is not the `#1C1B1F` canvas, so
the plate reads as a rectangle. The hidden-content control makes it much worse:
`img.hidden_expand_opt` carries `padding: 12px; margin: -12px !important`, so its
40×40 box is pulled 12px up out of its paragraph and lands on the headword — the
article rendered `зооло` + box instead of `зоолог`. Its SVG glyph is only 24×24, so
everything outside the glyph is bare painted background.

The same file already solves this for the dictionary-emitted sense icons, which
are why `gd_tag_*` glyphs show no box today; the app's own control glyphs are
simply not in that selector list.

## What Changes

- Widen the existing "Inline article icon rendering" guarantee so it covers the
  app's **own** inline control glyphs — the hidden-content expand/collapse
  control and the pronunciation (audio) control — not only the inline icons a
  dictionary emits. They SHALL draw no background box in either theme.
- Add the matching CSS to the article's injected stylesheet, in the same idiom and
  beside the existing `gd_tag_*` override it must out-specify.
- State explicitly that the light plate stays for dictionary **content** images
  (photographs, illustrations), so this cannot later be "fixed" in the wrong
  direction by removing the plate altogether.

- **Not in scope:** changing DarkReader's configuration or removing the
  dark-mode plate injection. Both were considered and rejected in `design.md`;
  the plate is correct for content images and DarkReader is what makes arbitrary
  dictionary CSS legible at all.
- **Not in scope:** the headword/expander geometry itself. The expander's
  negative margin is intentional (it enlarges the tap target) and is not what is
  broken; the invisible background is.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: "Inline article icon rendering" is widened from dictionary-emitted
  inline icons to all inline article icons the app renders itself, with the
  no-background-box guarantee stated for both themes, and with an explicit
  statement that content images keep the light plate.

## Impact

- `app/EngineController.cpp` — the injected article CSS block that already
  carries the `gd_tag_*` transparent-background override gains a rule for the
  app's control glyphs. No engine or `carve/` change.
- Verification is on-device and computable: the article document's
  `getComputedStyle` for the two images must report a transparent background in
  both themes, and a screenshot of an article with a hidden zone must show the
  complete headword in dark mode.
- `docs/TESTING.md` — one row for the dark-theme control-icon check.