## 1. Implementation

- [x] 1.1 Add `_headword_span` (the match span) and route `_example_shows_word` through it
- [x] 1.2 Shorten an over-long example to the headword's sentence, then to a window centred on the headword, marking cut edges
- [x] 1.3 Pass the headword and forms from `_sense_examples`

## 2. Tests and docs

- [x] 2.1 Cover the headword past the bound, the no-sentence-break window, and the no-headword fallback
- [x] 2.2 Run `python -m unittest scripts.tests.test_kaikki_to_dsl`
- [x] 2.3 Update `docs/KAIKKI-CONVERSION.md`
- [x] 2.4 `openspec validate example-keeps-headword-sentence --strict`
