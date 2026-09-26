## 1. Test fixture — a DSL entry with a hidden zone

- [x] 1.1 Add a headword entry that uses the DSL optional/hidden zone (`[*]…[/opt]`) to `scripts/make-example-dicts.py` so the generated `examples/dictionaries/aurelex-*.dsl` fixtures cover it, and regenerate the committed `.dsl` / `.dsl.dz` files (satisfies the `sample-dictionaries` "Example dictionaries cover DSL optional content" requirement)
- [x] 1.2 Confirm the generated entry is picked up by the existing smoke flow (the `aurelex-basic.dsl.dz` + nested `aurelex-lingvo.dsl` fixtures the `engine smoke` workflow stages) and that the new headword does not disturb the existing `smoke` / `book` assertions

## 2. Engine-markup regression guard

- [x] 2.1 Add a smoke assertion in `carve/smoke/main.cpp` that a lookup of the hidden-zone headword yields HTML containing `class="dsl_opt"` and `gdExpandOptPart(`, printed in the existing `NAME=OK|FAIL` style
- [x] 2.2 Add the matching `grep` gate to `.github/workflows/engine-smoke.yml` so a future upstream bump that stops emitting the expander fails CI instead of silently shipping a dead control (design D1/D2 depend on this markup staying put)
- [x] 2.3 Run the host smoke build locally (`-DAURELEX_BUILD_SMOKE=ON`) and confirm the new assertion passes

## 3. Article-side toggle script

- [x] 3.1 Add `app/android/assets/scripts/gd-article-controls.js` defining `window.gdExpandOptPart(expanderId, optionalId)` with upstream's semantics: `alt` flag `[+]`/`[-]`, icon swap, `display:inline`/`none` over the `.dsl_opt` zones inside the named `gd-<dictId>` section (design D3)
- [x] 3.2 Resolve the swapped icon URLs from the loopback origin derived from `document.currentScript.src`, never a literal `qrc:///` path (design D2) — the collapse state must show a real image, not a broken one
- [x] 3.3 Make the function a no-op-safe global: it must be callable from an inline `onclick` attribute (bubble phase, `window` scope) and must not throw when the expander or the section id is missing

## 4. Article HTML wiring

- [x] 4.1 Inject `<script src="<base>/scripts/gd-article-controls.js"></script>` from the always-on controller block in `EngineController::rewriteArticleUrls`, alongside the existing `darkreader.js` script tag
- [x] 4.2 Leave `gd-builtin.js` in the `stripScripts` list — it is the desktop bridge and must keep being removed (design D1)
- [x] 4.3 Add a `.hidden_expand_opt` touch-target override to the injected `<style>` block next to `plainCss`: keep the 16px glyph, grow the tappable box with padding and negative margin (design D4)
- [x] 4.4 Verify the loopback asset route serves the new script (`ArticleServer::classify` → `assets:/scripts/…`) and that `expand_opt.svg` / `collapse_opt.svg` both resolve from `assets:/icons/`
- [x] 4.5 Confirm no other rewrite step drops the injected script or the `.hidden_expand_opt` img (the `plainCss`/dark-mode style removers use narrow regexes — check the new CSS does not collide with them)

## 5. On-device verification

- [ ] 5.1 With a hidden-zone dictionary imported, confirm the expander renders as a visible icon (not a broken image) at first render, with the zone collapsed
- [ ] 5.2 Tap it: the hidden content appears in place and the control switches to the collapsed icon
- [ ] 5.3 Tap again: the content hides again
- [ ] 5.4 Confirm a back/forward re-render resets the reveal to collapsed — the behavior pinned by the "Re-rendering the article restores the collapsed state" scenario — and confirm a revealed zone SURVIVES the zoom and dark-mode toggles (those run in-place JS against the live document, not a re-render, per the design's risk note)
- [ ] 5.5 Tap a link inside revealed content and confirm it performs an in-app lookup (no WebView navigation away, no `preventDefault` conflict with the QML click probe at `app/main.qml:2502`)
- [ ] 5.6 Confirm a headword whose entry has no hidden zone shows no control and renders unchanged
- [ ] 5.7 Check the control stays legible in both light and dark mode under Dark Reader; if it is recolored, add it to the Dark Reader ignore list rather than disabling Dark Reader

## 6. Documentation

- [x] 6.1 Add the control to the accessible element ID table in `AGENTS.md` (`alt="[+]"` / `alt="[-]"` surfaces as `content-desc` through the WebView's DOM accessibility subtree, so it is addressable from UIAutomator like the suggestion panel)
- [x] 6.2 Note in the change that no localization catalogs are touched: the control is icon-only and the `alt` text stays the upstream `[+]`/`[-]`
