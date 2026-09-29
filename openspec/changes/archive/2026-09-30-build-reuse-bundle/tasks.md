## 1. Option and verification

- [x] 1.1 Add `--reuse-bundle` to the build parser
- [x] 1.2 Add a helper that reads an existing bundle's entry names (zip central directory or directory listing)
- [x] 1.3 In `build()`, when the option is given, skip writing the bundle and instead verify that every name the bundle must hold is present, reporting missing names or an absent bundle
- [x] 1.4 Keep the default path (bundle built) unchanged

## 2. Tests

- [x] 2.1 Reusing a complete bundle leaves it byte-for-byte unchanged and reports the reuse
- [x] 2.2 A referenced resource missing from the reused bundle is warned about and counted
- [x] 2.3 An absent bundle is reported
- [x] 2.4 Without the option, the bundle is still rebuilt

## 3. Validation

- [x] 3.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 3.2 Run `openspec validate build-reuse-bundle --strict` and resolve any findings
