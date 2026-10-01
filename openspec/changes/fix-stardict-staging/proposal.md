## Why

StarDict is listed as a supported format, the engine reads it, and the CI smoke
test covers it — but **no StarDict dictionary can actually be imported**. A
StarDict dictionary is a set of sibling files sharing a basename: `.ifo`
(header), `.idx` (index) and `.dict` (definitions), plus an optional `.syn`.
The importer's supported-name filter accepts only `.ifo`, so a picked folder is
stage-copied with the header and *without the payload*. The engine then fails
with "No corresponding .idx file was found for …" and the dictionary is
recorded as a load failure.

The result is a format the app advertises and cannot load, and — because
StarDict is the one format `pyglossary` can write — a broken bridge for every
other format a user might bring.

## What Changes

- The importer's supported-dictionary-name filter accepts a StarDict
  dictionary's companion files (`.idx`, `.dict`, `.syn` and the compressed
  variants the engine resolves), so a picked StarDict set is staged whole.
- The remote catalog's dictionary-extension list mirrors the same set, so a
  catalog entry may declare a StarDict dictionary's companions and have them
  installed and detected as present.
- Add automated coverage that the classification accepts a complete StarDict
  set and still rejects unsupported formats, and that the two lists agree.

Non-goals: adding any format that is not already compiled and read successfully
today. XDXF is compiled into the carve but not wired, and BGL/EPWING/etc. remain
conversion targets; none of that is in scope here.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: the "Dictionary folder selection and scanning"
  requirement states which files are stage-copied and therefore must list the
  StarDict companion files; a new scenario covers importing a StarDict
  dictionary end to end.

## Impact

- `app/android/src/org/aurelex/pocket/dictionary/AurelexActivity.java` — the
  staging filter (`isSupportedDictionaryName`).
- `app/RemoteCatalog.cpp` / `RemoteCatalog.hpp` — `kDictionaryExtensions` and
  `kDictionaryExtensionCount`, used for catalog install validation and
  installed-detection.
- `app/tests/CatalogTest.cpp` + `app/tests/fixtures/` — classification coverage.
- Docs that state the supported file set: `docs/TESTING.md` (the StarDict
  limitation entry), `README.md` (the format table), and the
  `dictionary-management` spec itself.
- No engine change, no patch, no boundary change. The engine's StarDict reader
  is already compiled (`carve/CMakeLists.txt`) and exercised by the CI smoke
  test (`scripts/make-smoke-stardict.py`), which feeds the engine a complete
  directory and therefore never hits the staging filter.

## Risks

- The Java staging filter and the C++ catalog list are two copies of the same
  knowledge and can drift. This change adds a test on the C++ side and a comment
  cross-reference; it does not unify them.
- Matching on bare extensions (`.idx`, `.dict`) will also copy unrelated files
  that happen to share those names. That is benign — the engine ignores files
  with no `.ifo` — and is much simpler than a basename-sibling rule, but it is a
  deliberate trade-off recorded in `design.md`.
