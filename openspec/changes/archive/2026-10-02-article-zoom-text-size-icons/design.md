## Context

See `proposal.md` — Why. The article toolbar's zoom controls are two
`ToolButton`s in `app/main.qml` that render glyphs from the app's classic
Material Icons font via the `icon()` map (`zoom_in` U+E8FF, `zoom_out`
U+E900), alongside Back / Forward / Favorites. The app already ships a second,
tiny icon font — the Material Symbols Outlined subset
(`app/res/fonts/MaterialSymbols-Outlined-subset.ttf`, family "Material Symbols
Outlined") — because three earlier controls needed Material Symbols-only
glyphs (`folder_open`, `match_word`, `light_mode_auto`). The subset recipe was
a one-off: `docs/TESTING.md` names `build_symbol_subset.py`, but that script is
not in the repo, so the font was not reproducible from the tree.

## Goals / Non-Goals

**Goals:**

- The zoom controls read as "change article text size", using the Material
  Symbols `text_increase` / `text_decrease` glyphs.
- The secondary font stays a few KB and keeps the classic font's 1.0 em
  vertical metrics, so mixing families never shifts a sibling label.
- The subset becomes reproducible from the repo.

**Non-Goals:**

- Any change to zoom behavior, range, step, persistence, or accessible names.
- Adding new UI controls, a zoom-percentage label, or per-article zoom.
- Touching the engine, the `gd_*` boundary, or `patches/`.

## Decisions

**D1 — Use the Material Symbols `text_increase` / `text_decrease` glyphs
(from the secondary subset), not a classic-font glyph.**
The classic Material Icons file has no text-size glyph; the closest it offers
is the magnifier the toolbar is replacing. Name → codepoint comes from the
authoritative upstream list
(`MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints`):
`text_decrease` U+EADD, `text_increase` U+EAE2. Both are in the BMP, so the
existing `String.fromCodePoint` helper handles them with no change.

**D2 — Reject the `fonts.gstatic.com/render/.../text_increase.kt` URL as a
font source.** As recorded in the tri-state-theme-control design D6, despite
the `.kt` suffix it returns Compose `ImageVector` Kotlin source, not an sfnt
binary. The upstream variable font plus the `.codepoints` list stays the
single source of truth.

**D3 — Re-subset all five glyphs from upstream v2.973 rather than merge two
fonts.** An incremental merge of the two new outlines into the existing subset
would create a second provenance path for one file. Rebuilding at the same
axis instance (`opsz 24`, `wght 400`, `FILL 0`, `GRAD 0`) produced outlines
byte-identical to the existing subset for `folder_open`, `match_word`, and
`light_mode_auto`, so the verified dock/theme and groups glyphs do not change.

**D4 — Commit the recipe as `scripts/build_symbol_subset.py`.** The script
instances the upstream variable font, subsets to the codepoints in one `GLYPHS`
map, and re-normalizes the metrics (see D5). It downloads the upstream font if
no `--source` is given and prints the resulting codepoints so a wrong name
cannot pass silently.

**D5 — Keep the 1.0 em metric normalization.** The upstream subset carries
`hhea` ascent 1056 / descent −96 on `upm 960` (a 1.2 em line box) against the
classic font's 1.0 em. The rebuild pins `hhea`/OS-2 `asc = upm`, `desc = 0`,
`lineGap = 0`, sets `USE_TYPO_METRICS`, and zeroes the `post` underline. The
toolbar mixes no families inside one `Text`, but the dock's theme cell does,
and the app ships one subset for both.

## Risks / Trade-offs

- **A wrong-but-real codepoint renders the wrong icon silently** → the
  codepoints come from the upstream authority and were verified on device: the
  toolbar shows "A−" / "A+" at 20 px, not tofu.
- **A stale font survives in the APK** → bundled resources are declared with
  `qt_add_resources` (not `.qrc` + AUTORCC), whose `FILES` entries are real
  build inputs; the rebuild re-ran `rcc_fonts` and repackaged.
- **Rebuilding all five glyphs could shift the verified three** → compared
  pre- and post-build glyph outlines; the three pre-existing glyphs are
  byte-identical.
