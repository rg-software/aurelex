## 1. About headword

- [x] 1.1 Build the about article's headword as `About <name>` (the dictionary's `#NAME`)

## 2. Annotation file

- [x] 2.1 Add `write_annotation(path, name, source_lang_name, source_lang, dump_date)` writing the attribution as plain text
- [x] 2.2 In `build()`, write `<out-dir>/<name>.ann` beside the dictionary, on every run (including `--sample` and `--reuse-bundle`)

## 3. Tests

- [x] 3.1 The about article's headword is `About <name>` for the build's name
- [x] 3.2 The annotation file exists beside the dictionary, names the dictionary, and carries the license and source; it is written with `--reuse-bundle` too
- [x] 3.3 Update the about-headword filter in the test helpers

## 4. Documentation

- [x] 4.1 Update the output-layout / attribution note in `docs/KAIKKI-CONVERSION.md`

## 5. Validation

- [x] 5.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 5.2 Run `openspec validate dictionary-annotation --strict` and resolve any findings
