## 1. Russian profile

- [x] 1.1 Add the Russian form vocabulary `_RU_FORM_TAGS` and short labels `_RU_SHORT_TAGS`
- [x] 1.2 Add `_RU_NOISE` (register/table plus canonical, romanization, class, error-*, and the derivational tags)
- [x] 1.3 Add `_RU_SENSE_NOISE` and reuse the shared sense abbreviations
- [x] 1.4 Register the `ru` entry in `LANG_PROFILES` with IPA pronunciation and audio enabled
- [x] 1.5 Drop a form whose label is empty in `collect_profile_forms`, so an unlabellable form is not printed bare

## 2. Tests

- [x] 2.1 `get_lang_profile("ru")` returns a profile without a fallback warning
- [x] 2.2 A Russian case/number form qualifies and is labelled with its short tags
- [x] 2.3 A canonical/romanization/derivational form is disqualified, and an unlabellable form is dropped
- [x] 2.4 An unknown language still falls back and reports it
- [x] 2.5 Existing profile tests still pass

## 3. Validation

- [x] 3.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 3.2 Run `openspec validate russian-language-profile --strict` and resolve any findings
