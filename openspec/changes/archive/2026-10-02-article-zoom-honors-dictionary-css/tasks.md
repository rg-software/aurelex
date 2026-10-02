## 1. Correct the zoom contract

- [x] 1.1 Rewrite "Article zoom reflows to the screen width" in the delta spec to state what
      zoom scales (text inheriting the root size) and what it does not (an absolute size a
      dictionary's own stylesheet sets), with the reason it is not forced (design D1, D2)
- [x] 1.2 Add a scenario asserting the pinned-size case, so the behaviour is required rather
      than tolerated
- [x] 1.3 Add a scenario asserting the converse — same format, no absolute sizes, scales
      normally — so the limitation cannot be mis-read as a format difference (design D3)
- [x] 1.4 Keep the unchanged scenarios (reflow, no horizontal slider, applies to every
      article) with their existing wording intact

## 2. Correct the test document

- [x] 2.1 `docs/TESTING.md` §"Article zoom & reflow": note that zoom scales text inheriting
      the root size, and that a dictionary pinning absolute sizes (named: `collinslaw`) does
      not respond — with the CDP measurement as the evidence
- [x] 2.2 Add a check that the *root* font-size doubles even when the dictionary's own text
      does not, so a future failure of the mechanism is distinguishable from this limitation
- [x] 2.3 Adjust §18c/§18g so they no longer read as "zoom always scales"; point them at a
      fixture that does scale (Black's Medical `.mdx` or a DSL fixture) for the generic check
- [x] 2.4 Record the `collinslaw` trip case in the "things that look like bugs and are not"
      list in that section, with the declaration that causes it

## 3. Checks

- [x] 3.1 `openspec validate article-zoom-honors-dictionary-css --strict` passes
- [x] 3.2 Confirm no `qsTr` string or `strings.xml` entry changed — no
      `scripts/update-translations.ps1` run, no `values-ru`/`values-ja` edit
- [x] 3.3 Confirm no application code changed: the delta touches specs and docs only
- [x] 3.4 Re-run the CDP measurement after the docs land, confirming the numbers quoted in
      the proposal and in `docs/TESTING.md` still reproduce
