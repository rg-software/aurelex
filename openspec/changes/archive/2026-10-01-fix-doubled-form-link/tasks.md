## 1. Fix the doubling

- [x] 1.1 In `_link_form_targets`, collect the distinct targets from `alt_of` and `form_of` and wrap each once
- [x] 1.2 In `unlink_absent_refs`, strip `[ref]`/`[/ref]` from the substituted text so unlinking never leaves link markup

## 2. Tests

- [x] 2.1 A target named by both `alt_of` and `form_of` yields a single `[ref]…[/ref]`
- [x] 2.2 Unlinking an absent target removes any nested link markup
- [x] 2.3 Existing link, cross-reference, and card-quality tests still pass

## 3. Validation

- [x] 3.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 3.2 Run `openspec validate fix-doubled-form-link --strict` and resolve any findings
