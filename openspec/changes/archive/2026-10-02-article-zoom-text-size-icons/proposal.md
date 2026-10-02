## Why

The article toolbar's zoom controls use the generic magnifier glyphs (`zoom_in`
U+E8FF / `zoom_out` U+E900) from the classic Material Icons font. Next to
Back / Forward / Favorites, a magnifier reads as *page* zoom or search rather
than "make the article text bigger", which is what the controls actually do.
The Material Symbols `text_increase` / `text_decrease` glyphs (an "A…" with a
plus/minus) state the action directly.

## What Changes

- **Article toolbar zoom icons change** from `zoom_in` / `zoom_out` to the
  Material Symbols `text_increase` (U+EAE2) / `text_decrease` (U+EADD)
  glyphs. The controls keep their behavior (`engine.setArticleZoom` +/-
  one step), their disabled-at-bounds rules, and their accessible names
  ("Zoom in" / "Zoom out").
- **The secondary icon subset is regenerated** to carry five glyphs instead of
  three (`folder_open`, `match_word`, `light_mode_auto`, plus `text_decrease`
  and `text_increase`), rebuilt from the upstream Material Symbols Outlined
  variable font at the `opsz 24 / wght 400 / FILL 0 / GRAD 0` instance and
  re-normalized to the classic font's 1.0 em vertical metrics.
- **The subset recipe is committed** as `scripts/build_symbol_subset.py`.
  `docs/TESTING.md` already refers to this script, but it was never checked in,
  so the current subset was not reproducible from the repo.

No behavior, storage, network, permission, or dependency changes.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `lookup`: the "Article zoom reflows to the screen width" requirement now
  names the control iconography — the zoom controls are labelled with
  text-size increase/decrease icons rather than generic magnifiers.

## Impact

- **QML** (`app/main.qml`): drop `zoom_in`/`zoom_out` from the classic
  `icon()` map; add `text_decrease`/`text_increase` to `symbolIcon()`; point
  the two toolbar `ToolButton`s at `symbolIcon(...)` + `symbolFontFamily`.
- **Font asset** (`app/res/fonts/MaterialSymbols-Outlined-subset.ttf`):
  regenerated (2.4 KB, five glyphs; the three pre-existing outlines stay
  byte-identical).
- **Scripts**: new `scripts/build_symbol_subset.py` (instance → subset →
  normalize metrics), replacing the undocumented one-off build.
- **C++ comment** (`app/main.cpp`): the font-registration comment lists the
  subset's glyphs.
- **Accessibility / test IDs**: unchanged — `Accessible.name` stays
  `"Zoom out"` / `"Zoom in"`, so the AGENTS.md table rows do not move.
- **Localization**: icon-only change, no new user-visible English.
- **No** engine, `gd_*` boundary, carve, or `patches/` change.
