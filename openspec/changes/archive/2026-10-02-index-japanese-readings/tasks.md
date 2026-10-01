## 1. Implementation

- [x] 1.1 `reading_words(record, profile)`: the record's readings as lookupable kana
- [x] 1.2 Fold readings to hiragana; drop separators; de-duplicate
- [x] 1.3 `--index-readings` flag; `emit()` adds the readings as extra headwords

## 2. Tests and docs

- [x] 2.1 `reading_words` unit test (separators, annotation, katakana → hiragana, de-dup)
- [x] 2.2 Build test: off by default, not affected by `--include-inflections`, on with `--index-readings`
- [x] 2.3 `python -m unittest scripts.tests.test_kaikki_to_dsl`
- [x] 2.4 Update the CLI help and `docs/KAIKKI-CONVERSION.md`
- [x] 2.5 Verified on a 200-headword ja sample (302 headwords, hiragana readings)
- [x] 2.6 `openspec validate index-japanese-readings --strict`
