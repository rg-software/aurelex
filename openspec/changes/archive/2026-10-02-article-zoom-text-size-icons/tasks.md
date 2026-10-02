## 1. Secondary icon subset

- [x] 1.1 Add `text_decrease` (U+EADD) and `text_increase` (U+EAE2) to the subset alongside the existing `folder_open`, `match_word`, and `light_mode_auto`; source the codepoints from the upstream `MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints` file.
- [x] 1.2 Commit the recipe as `scripts/build_symbol_subset.py`: instance the upstream variable font at `opsz 24 / wght 400 / FILL 0 / GRAD 0`, subset to the `GLYPHS` codepoints, re-normalize `hhea`/OS-2 metrics to 1.0 em (`asc = upm`, `desc = 0`, `USE_TYPO_METRICS`) and zero the `post` underline. It downloads the upstream font when `--source` is omitted and prints the surviving codepoints.
- [x] 1.3 Regenerate `app/res/fonts/MaterialSymbols-Outlined-subset.ttf`; verify it holds all five codepoints, is a few KB (2.4 KB), and that the `folder_open`/`match_word`/`light_mode_auto` outlines are byte-identical to the previous file (verified: identical).

## 2. Toolbar wiring

- [x] 2.1 Remove the now-unused `zoom_in` / `zoom_out` entries from the classic `icon()` map in `app/main.qml`.
- [x] 2.2 Add `"text_decrease": 0xeadd` and `"text_increase": 0xeae2` to the `symbolIcon()` map and update its comment.
- [x] 2.3 Point the two article-toolbar zoom `ToolButton`s at `root.symbolIcon(...)` + `root.symbolFontFamily`; leave behavior (`engine.setArticleZoom` ± step), the disabled-at-bounds bindings, the 20 px size, and the `Accessible.name` ("Zoom out" / "Zoom in") unchanged.
- [x] 2.4 Update the font-registration comment in `app/main.cpp` to list the subset's five glyphs.

## 3. Verification and documentation

- [x] 3.1 Build with `app/build.ps1 -Configuration Debug -Install` and verify on device: the toolbar shows text-size decrease/increase icons (not a magnifier, not tofu), and zooming still works with each control disabled at its bound. (Verified on device: the controls render "A−" / "A+"; the `rcc_fonts` resource rebuilt and repackaged.)
- [x] 3.2 Run `openspec validate article-zoom-text-size-icons`.
- [x] 3.3 Update `docs/TESTING.md`'s secondary-icon-font note to record that the subset now carries five glyphs (text-size icons included) and that it is reproducible via `scripts/build_symbol_subset.py`. Confirm the AGENTS.md accessible-element table still matches (zoom names are unchanged, so no row edit is expected).
- [x] 3.4 Localization no-op check: no `qsTr`/`tr` call site or `app/android/res/values*/strings.xml` string changed (the change is icon-only and `Accessible.name` is unchanged), so `app/i18n/*` needs no update.
