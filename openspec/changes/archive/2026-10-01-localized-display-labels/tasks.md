## 1. Profile POS labels

- [x] 1.1 Add `pos_labels` to `LangProfile` (empty by default) and use it at the `[p]` render site
- [x] 1.2 Give the Russian profile `pos_labels` (сущ., гл., прил., …)

## 2. Russian sense abbreviations

- [x] 2.1 Add `_RU_SENSE_SHORT` (Russian) and use it in the Russian profile instead of the English set

## 3. Tests

- [x] 3.1 A Russian record's part of speech renders with the Russian label
- [x] 3.2 A Russian sense tag renders with the Russian abbreviation
- [x] 3.3 English is unchanged (an unmapped profile shows the raw code)
- [x] 3.4 Existing profile and render tests still pass

## 4. Validation

- [x] 4.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 4.2 Run `openspec validate localized-display-labels --strict` and resolve any findings
