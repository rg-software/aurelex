## 1. Readings as a profile concept

- [x] 1.1 `LangProfile` gains `reading_tags`, `reading_marks`, `reading_default`
- [x] 1.2 `collect_profile_forms` skips reading forms; new `collect_profile_readings` groups them by mark
- [x] 1.3 `ja` maps go-on/kan-on/to-on → 音, kun/ko-kun → 訓, unclassified → 読み

## 2. Rendering

- [x] 2.1 The readings line is emitted under the part of speech, or hoisted once when the card's records agree
- [x] 2.2 Update the `render_card` docstring

## 3. Tests, docs, validation

- [x] 3.1 Grouping, the default mark, and "not an inflection" tests
- [x] 3.2 `python -m unittest scripts.tests.test_kaikki_to_dsl`
- [x] 3.3 Update `docs/KAIKKI-CONVERSION.md`
- [x] 3.4 Render real ja entries to confirm the line reads as intended
- [x] 3.5 `openspec validate japanese-readings-line --strict`
