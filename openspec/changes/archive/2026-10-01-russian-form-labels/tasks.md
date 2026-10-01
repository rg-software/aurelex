## 1. Russian form labels

- [x] 1.1 Replace `_RU_SHORT_TAGS` with the Russian Cyrillic abbreviations

## 2. Tests

- [x] 2.1 Update the expected Russian form labels in the profile tests
- [x] 2.2 Existing profile and render tests still pass

## 3. Validation

- [x] 3.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 3.2 Run `openspec validate russian-form-labels --strict` and resolve any findings
