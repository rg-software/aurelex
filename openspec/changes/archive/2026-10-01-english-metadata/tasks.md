## 1. English metadata

- [x] 1.1 Add an English language-name table and have `_language_name` prefer it, falling back to the source's name then the code
- [x] 1.2 Drop the language word from the description's first line (`<title>: a Wiktionary-based dictionary`)

## 2. Tests

- [x] 2.1 A build from a record whose `lang` is non-English names the language in English in the headers, about article and annotation
- [x] 2.2 An unlisted language falls back to the source's name
- [x] 2.3 Existing tests still pass

## 3. Validation

- [x] 3.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 3.2 Run `openspec validate english-metadata --strict` and resolve any findings
