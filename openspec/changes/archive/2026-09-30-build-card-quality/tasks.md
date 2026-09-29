## 1. Detect split headwords

- [x] 1.1 Extend the full-build selection to also return the headwords whose records start more than one run in the snapshot, reusing the existing single pass
- [x] 1.2 Fold the indexed-headword set and the split detection into one selection call, subsuming the old single-purpose selection (which had no other callers)

## 2. Merge and filter cards

- [x] 2.1 In the render pass, set aside records of a split headword and render each such headword once from all its records, in first-seen order
- [x] 2.2 Collect rendered cards as `(headwords, body, word, record_count)` instead of appending to `out_lines` immediately
- [x] 2.3 Drop a card whose body has no gloss unless its headword is linked by another card; keep linked ones
- [x] 2.4 Unlink any remaining `[ref]…[/ref]` whose target is not an emitted headword, keeping the text
- [x] 2.5 Assemble the dictionary text from the surviving cards; count cards and kept records from them

## 3. Reporting

- [x] 3.1 Add the merged-headword, omitted-card, and unlinked-reference counts to `Report` and its summary

## 4. Tests

- [x] 4.1 A headword whose records are not adjacent in the snapshot is emitted once, carrying all their content
- [x] 4.2 A card with no gloss and no link is omitted and counted
- [x] 4.3 A card with no gloss that another card links to is kept, and the link resolves
- [x] 4.4 No emitted `[ref]` targets a headword the dictionary does not contain
- [x] 4.5 Existing card-layout, cross-reference, and sample tests still pass

## 5. Validation

- [x] 5.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 5.2 Run `openspec validate build-card-quality --strict` and resolve any findings
