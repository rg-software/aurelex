## 1. Renderer

- [x] 1.1 Pass the card's headword list from `emit()` into `render_card()` as an
      optional parameter, keeping `render_record()` and all existing callers
      working without it. Verify: the existing unit tests pass unmodified.
- [x] 1.2 Prepend `\t[b]<escaped primary headword>[/b]` as the first body line
      if and only if the card has more than one headword. Verify: unit test
      with an alias card (readings) shows the title first, and a
      single-headword card's body is byte-identical to before.

## 2. Tests and docs

- [x] 2.1 Unit tests: title on a readings-alias card, title on an
      inflections-alias card, no title on a single-headword card, determinism
      (same input renders the same bytes twice). Verify: `python -m unittest
      discover -s scripts/tests` passes.
- [x] 2.2 Document the title rule in the article-shape section of
      `docs/KAIKKI-CONVERSION.md`, including the single-headword scoping.
      Verify: the doc states when the title appears and that base-only cards
      are unchanged.

## 3. Verification

- [x] 3.1 Build a ja sample with `--index-readings` and confirm the 喧伝 card
      opens with its 喧伝 title, a base-only card carries no title, and the
      preview renders with balanced tags. Verify: inspect the sample `.dsl`
      and `.preview.html`.
