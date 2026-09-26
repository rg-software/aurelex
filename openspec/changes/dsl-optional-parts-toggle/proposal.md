## Why

DSL dictionaries hide content authors marked as optional — the `[*]…[/opt]` "hidden zone" (answers, notes, extra examples) — behind a tappable `[+]` expander, rendered by the upstream engine as a `<span class="dsl_opt">` plus an `<img class="hidden_expand_opt" onclick="gdExpandOptPart(...)">`. In Aurelex that expander is inert: `EngineController::rewriteArticleUrls` strips `scripts/gd-builtin.js` from every article (the desktop link/active-article bridge we do not need), and that file is the only place `gdExpandOptPart` is defined. The stylesheet still applies the default `.dsl_opt { display: none; }`, and the boundary never turns on `optPartsAutoExpand`, so the content behind the icon is hidden with no working way to reveal it. Users of DSL dictionaries (e.g. the `kaikki-to-dsl` corpus) silently lose whatever the dictionary chose to hide.

## What Changes

- Bundle a small article-side script in the app assets that implements the hidden-zone expander, and stop stripping it from the article HTML.
- Serve the expander's collapse/expand icons to the article web view (the upstream `expand_opt.svg` / `collapse_opt.svg` are already in the APK assets but are never swapped in because no handler runs).
- Nothing changes in the engine: the markup, the `dsl_opt` / `hidden_expand_opt` CSS classes, and the `.dsl_opt { display: none; }` default all stay upstream. This is boundary work only — no `patches/` entry, no upstream delta.

## Capabilities

### New Capabilities
<!-- Capabilities being introduced. Use kebab-case for path segments you introduce
     (e.g. user-auth or identity/user-auth) that follow the project's existing
     spec organization. Each creates specs/<capability-path>/spec.md. -->
- `sample-dictionaries`: the generated example DSL dictionaries guarantee
  coverage of the DSL optional/hidden zone, so the hidden-content toggle is
  testable against the committed fixtures instead of only against a
  hand-built dictionary.

### Modified Capabilities
<!-- Existing capabilities whose REQUIREMENTS are changing (not just implementation).
     Only list here if spec-level behavior changes. Each needs a delta spec file.
     Use the exact existing path under openspec/specs/. Leave empty if no requirement
     changes. A change with no capabilities at all (pure refactor, tooling, docs)
     must set `skip_specs: true` in its .openspec.yaml - openspec validate rejects
     a zero-delta change without that marker. Do not invent a requirement just to
     satisfy validation. -->
- `lookup`: article rendering gains a requirement that dictionary content the author marked hidden is collapsed behind a tappable control the user can show and re-hide, and that the toggle works inside the inline article surface.

## Impact

- Affected code:
  - `app/EngineController.cpp` — `rewriteArticleUrls` (asset/script handling and the injected article-side controller block).
  - `app/android/assets/scripts/` — new article-side script.
  - `app/android/assets/icons/expand_opt.svg` + `collapse_opt.svg` — already bundled; now actually referenced by the article page.
  - `carve/gd_boundary.cc` — unchanged; confirms the engine's default (collapsed, no auto-expand) is what we want.
  - `scripts/make-example-dicts.py` — the generated fixtures gain a hidden-zone
    entry, and the committed `.dsl` / `.dsl.dz` files are regenerated.
- Affected APIs: none. No `gd_*` boundary function is added or changed.
- Affected dependencies: none. No new engine source, no patch, no upstream bump.
- Upstream fidelity: `engine/` stays byte-for-byte at the pinned tag.
- Localization: none. The control is an icon, not text, so no `qsTr` / `strings.xml` catalog entries.
