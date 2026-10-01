## 1. Help

- [x] 1.1 Add a `Modes:` block to the build parser's description listing the three modes and the per-mode `--help` pointer

## 2. Validation

- [x] 2.1 `python scripts/kaikki-to-dsl.py --help` shows the modes under the usage line (and each `<mode> --help` still works)
- [x] 2.2 Run `python -m unittest scripts.tests.test_kaikki_to_dsl`
