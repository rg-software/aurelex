## 1. Japanese profile

- [x] 1.1 Japanese `pos_labels` (名詞, 動詞, 形容動詞, 助詞, …)
- [x] 1.2 Readings labelled as readings (読み/呉音/漢音/訓…), conjugation-class tags dropped from the label
- [x] 1.3 Japanese conjugation labels (未然形, 連用形, 終止形, …) and sense-tag labels (比喩, 口語, 俗語, 方言, …)

## 2. Profile-driven audio

- [x] 2.1 `build` fetches no audio archive when the profile declares no recordings
- [x] 2.2 `prefetch-audio` refuses for such a language

## 3. CJK example handling

- [x] 3.1 `。！？` end a sentence; CJK brackets/quotes are skipped as punctuation
- [x] 3.2 A CJK headword is matched as a substring, confined to CJK scripts

## 4. Tests, docs and validation

- [x] 4.1 Japanese label, reading and sense tests
- [x] 4.2 CJK sentence-bound test; no-archive test
- [x] 4.3 `python -m unittest scripts.tests.test_kaikki_to_dsl`
- [x] 4.4 Update `docs/KAIKKI-CONVERSION.md`
- [x] 4.5 Build a ja sample and confirm no English labels leak
- [x] 4.6 `openspec validate japanese-language-profile --strict`
