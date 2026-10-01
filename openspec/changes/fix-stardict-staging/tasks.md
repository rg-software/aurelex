## 1. Staging filter (Java)

- [ ] 1.1 Add the StarDict companion suffixes to
  `AurelexActivity.isSupportedDictionaryName` so a picked StarDict set is copied
  whole: `.idx`, `.idx.gz`, `.idx.dz`, `.dict`, `.dict.dz`, `.syn`, `.syn.gz`,
  `.syn.dz` — exactly the lower-cased set `engine/src/dict/stardict.cc:1723-1735`
  resolves (note: no `.dict.gz`; the compressed definitions form is dictzip only)
- [ ] 1.2 Comment the filter naming `kDictionaryExtensions` in `RemoteCatalog.cpp`
  as its twin and why they must stay identical, so the next reader sees the
  duplication rather than rediscovering it
- [ ] 1.3 Confirm the sibling `.files` resource-directory rule
  (`isResourceDirName`) and `.files.zip` handling are untouched, and that
  `stageTreeInto` still copies everything inside a resource tree

## 2. Catalog format list (C++)

- [ ] 2.1 Add the same eight suffixes to `kDictionaryExtensions` in
  `app/RemoteCatalog.cpp` and update `kDictionaryExtensionCount` to match
- [ ] 2.2 Comment the list naming the Java filter as its twin, and stating that
  the set is derived from the engine's StarDict reader rather than guessed
- [ ] 2.3 Confirm `isInstalled` still requires an entry's dictionary-role
  basenames to be present, so a StarDict catalog entry reports installed only
  once its `.ifo`, `.idx` and `.dict` have all landed

## 3. Automated coverage

- [ ] 3.1 Extend `app/tests/CatalogTest.cpp` to assert
  `isSupportedDictionaryName` accepts a complete StarDict set and each compressed
  companion (`.idx.gz`, `.idx.dz`, `.dict.dz`, `.syn`, `.syn.gz`, `.syn.dz`), and
  still rejects an unsupported set (`.bgl`, `.xdxf`, `.slob`)
- [ ] 3.2 Extend the manifest fixture(s) under `app/tests/fixtures/` only if a
  StarDict entry shape is not already covered; otherwise note why not
- [ ] 3.3 Build and run the host test target:
  `cmake --build build-app-tests --target catalog_test` then run it; confirm it
  fails before 2.1 and passes after
- [ ] 3.4 Confirm the engine-level StarDict path is still green (the CI smoke
  fixture `scripts/make-smoke-stardict.py` writes `smoke.ifo`/`.idx`/`.dict` and
  `carve/smoke/main.cpp` indexes and searches it) — no change expected, this is a
  regression check

## 4. Documentation

- [ ] 4.1 Remove the StarDict entry from the "Known gaps" list in
  `docs/TESTING.md` and drop the "Does not load yet" wording
- [ ] 4.2 Add a StarDict recipe to `docs/TESTING.md` (import a folder containing
  a StarDict set; expect it listed, searchable, and removable)
- [ ] 4.3 Update the `README.md` format table: StarDict status becomes works;
  `docs/REMOTE-CATALOG.md` if it states the supported extension set
- [ ] 4.4 Re-check the README conversion note, which currently routes users via
  `.mdx` because StarDict could not load — with this fix the pyglossary →
  StarDict path works and the note should be simplified

## 5. On-device verification

- [ ] 5.1 Import a folder containing a real StarDict dictionary and confirm it
  loads, is listed with its display metadata, and is searchable
- [ ] 5.2 Import a StarDict dictionary packaged with dictzip (`.dict.dz`) and
  confirm it loads
- [ ] 5.3 Import a folder containing only a StarDict `.ifo` (companions absent)
  and confirm the app reports a failed load rather than listing a broken entry
- [ ] 5.4 Remove a StarDict dictionary and confirm its staged files and index are
  deleted and lookups no longer return its words
- [ ] 5.5 Re-import a previously-failed StarDict folder on a device that already
  had the `.ifo`-only staged copy, and confirm the dictionary now loads without
  an app restart
- [ ] 5.6 If a StarDict entry exists in the remote catalog, install it and
  confirm installed-detection reports it only after all its files land

## 6. Record

- [ ] 6.1 Update the `dictionary-management` spec wording if the archived delta
  differs from what shipped, then archive the change
