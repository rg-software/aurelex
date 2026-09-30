## 1. Split the example filter

- [x] 1.1 Add `_example_is_bookkeeping` (the `Citations:` stub) and `_example_is_archaic` (long-s or the Early Modern/Middle English markers); keep `_example_is_usable` as their conjunction
- [x] 1.2 Rewrite `_sense_examples` to take `allow_archaic`, prefer the shortest modern-readable example, and fall back to the shortest archaic one only when none is readable and the flag is set

## 2. Carry the per-sense flag

- [x] 2.1 Extend `SenseEntry` with an "archaic allowed" boolean and compute it in `_group_senses` from the sense's usage tags (obsolete, dated, archaic)
- [x] 2.2 Thread the flag through the render loop into `_sense_examples`

## 3. Tests

- [x] 3.1 An archaic sense with only an archaic example shows it
- [x] 3.2 An archaic sense with both keeps the modern-readable example
- [x] 3.3 A modern sense still drops an archaic example
- [x] 3.4 A `Citations:` example is dropped even on an archaic sense
- [x] 3.5 Existing grouping and example tests still pass

## 4. Validation

- [x] 4.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 4.2 Run `openspec validate archaic-sense-example-fallback --strict` and resolve any findings
