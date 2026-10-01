## 1. Split

- [x] 1.1 Create `scripts/kaikki/` with one module per section seam
- [x] 1.2 Move `_SCRIPT_DIR` to `constants`, `TabularLog` to `snapshot`, `_resolve_inputs` to a new `inputs` module (breaks the build↔prefetch cycle)
- [x] 1.3 Fix `__file__`-relative paths (`_SCRIPT_DIR`, `_ICON_ASSET_DIR`) for the package's new depth
- [x] 1.4 Per-module imports computed from the AST; dotted stdlib imports kept whole (`urllib.request`, `importlib.util`)

## 2. Facade and entry points

- [x] 2.1 `kaikki/__init__.py` re-exports every name and propagates attribute writes to the submodules
- [x] 2.2 `scripts/kaikki-to-dsl.py` is a launcher; add `kaikki/__main__.py`

## 3. Verification

- [x] 3.1 Point the test loader at the package; 188 test bodies unchanged
- [x] 3.2 `python -m unittest scripts.tests.test_kaikki_to_dsl` passes
- [x] 3.3 `python scripts/kaikki-to-dsl.py --help` and `prefetch-audio --help` work
- [x] 3.4 End-to-end sample build via the launcher
- [x] 3.5 Document the module map in `docs/KAIKKI-CONVERSION.md`
