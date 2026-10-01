## 1. Title option

- [x] 1.1 Add `--title` to the build parser (defaults to the output name)
- [x] 1.2 Use `--name`/`--title` for file paths and the title for `#NAME`, the about headword, and the description

## 2. Shared description

- [x] 2.1 Add `description_lines(title, language_name, language_code, dump_date, card_count)`
- [x] 2.2 Build the about article from it (as `[com]` lines under `About <title>`, plus the icon legend)
- [x] 2.3 Write the `.ann` from it; adopt the improved citation wording

## 3. Tests

- [x] 3.1 With `--title`, the files keep the output name while `#NAME`, the about headword, and the description heading use the title
- [x] 3.2 The annotation and the about article carry the same description lines
- [x] 3.3 Existing about/annotation/size tests still pass

## 4. Documentation

- [x] 4.1 Note the title/name split in `docs/KAIKKI-CONVERSION.md`

## 5. Validation

- [x] 5.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 5.2 Run `openspec validate dictionary-title --strict` and resolve any findings
