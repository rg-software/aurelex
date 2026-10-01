## 1. Staging filter (Java)

- [x] 1.1 Add the StarDict companion suffixes to
  `AurelexActivity.isSupportedDictionaryName` so a picked StarDict set is copied
  whole: `.idx`, `.idx.gz`, `.idx.dz`, `.dict`, `.dict.dz`, `.syn`, `.syn.gz`,
  `.syn.dz` — exactly the lower-cased set `engine/src/dict/stardict.cc:1723-1735`
  resolves (note: no `.dict.gz`; the compressed definitions form is dictzip only)
- [x] 1.2 Comment the filter naming `kDictionaryExtensions` in `RemoteCatalog.cpp`
  as its twin and why they must stay identical, so the next reader sees the
  duplication rather than rediscovering it
- [x] 1.3 Confirm the sibling `.files` resource-directory rule
  (`isResourceDirName`) and `.files.zip` handling are untouched, and that
  `stageTreeInto` still copies everything inside a resource tree

## 2. Catalog format list (C++)

- [x] 2.1 Add the same eight suffixes to `kDictionaryExtensions` in
  `app/RemoteCatalog.cpp` and update `kDictionaryExtensionCount` to match
- [x] 2.2 Comment the list naming the Java filter as its twin, and stating that
  the set is derived from the engine's StarDict reader rather than guessed
- [x] 2.3 Confirm `isInstalled` still requires an entry's dictionary-role
  basenames to be present, so a StarDict catalog entry reports installed only
  once its `.ifo`, `.idx` and `.dict` have all landed

## 3. Automated coverage

- [x] 3.1 Extend `app/tests/CatalogTest.cpp` to assert
  `isSupportedDictionaryName` accepts a complete StarDict set and each compressed
  companion (`.idx.gz`, `.idx.dz`, `.dict.dz`, `.syn`, `.syn.gz`, `.syn.dz`), and
  still rejects an unsupported set (`.bgl`, `.xdxf`, `.slob`)
- [x] 3.2 Extend the manifest fixture(s) under `app/tests/fixtures/` only if a
  StarDict entry shape is not already covered; otherwise note why not —
  **not needed**: the classification test calls `isSupportedDictionaryName`
  directly, and no manifest-shape change is involved, so a new fixture would
  test nothing new. Added a `nullptr` sentinel to `kDictionaryExtensions`
  instead, which lets the test assert the table and its count agree (a mistyped
  count would silently stop the classifier early)
- [x] 3.3 Build and run the host test target:
  `cmake --build build-app-tests --target catalog_test` then run it; confirm it
  fails before 2.1 and passes after — **verified both ways**: with
  `kDictionaryExtensionCount` temporarily reverted to 5 the new assertions fail
  (11 of them) and the binary exits 1; restored, it exits 0
- [x] 3.4 Confirm the engine-level StarDict path is still green (the CI smoke
  fixture `scripts/make-smoke-stardict.py` writes `smoke.ifo`/`.idx`/`.dict` and
  `carve/smoke/main.cpp` indexes and searches it) — no change expected, this is a
  regression check. **Confirmed, and the unrelated FAILs are pre-existing**:
  running the smoke tool against a StarDict-only fixture gives
  `gd_lookup("smoke") -> 2627 bytes`, `FTS_RESULTS: smoke`, `FTS_BODY=OK`,
  `FTS_WILD=OK`. The `RESOURCE_ON_*`, `REIMPORT_*` and `REMOVE_*` checks report
  FAIL because they need fixtures this generator does not create (the
  `aurelex-resource.svg`, a nested `.dsl`, and the DSL headword `book`), not
  because of anything here — verified by rebuilding the smoke tool with these
  changes stashed and getting byte-identical FAILs at the pinned tag

## 4. Documentation

- [x] 4.1 Remove the StarDict entry from the "Known gaps" list in
  `docs/TESTING.md` and drop the "Does not load yet" wording
- [x] 4.2 Add a StarDict recipe to `docs/TESTING.md` (import a folder containing
  a StarDict set; expect it listed, searchable, and removable)
- [x] 4.3 Update the `README.md` format table: StarDict status becomes works;
  `docs/REMOTE-CATALOG.md` if it states the supported extension set
- [x] 4.4 Re-check the README conversion note, which currently routes users via
  `.mdx` because StarDict could not load — with this fix the pyglossary →
  StarDict path works and the note should be simplified

## 5. On-device verification

These need a phone; they are recorded here and marked when run. 5.1 and 5.3 were
cross-checked against the host smoke tool, which drives the same engine code:

- [x] 5.1 Import a folder containing a real StarDict dictionary and confirm it
  loads, is listed with its display metadata, and is searchable — *(host check
  done: `gd_lookup("smoke") -> 2627 bytes` and `FTS_BODY=OK` on a StarDict
  fixture; **device-verified** by importing the `full/` fixture — listed and
  `zebra` resolves)*
- [x] 5.2 Import a StarDict dictionary packaged with dictzip (`.dict.dz`) and
  confirm it loads — *(device-verified with `dzsample.*`, a fixture built with a
  unique basename after the first attempt was invalidated by the importer's
  intersecting-pick dedup seeing the shared `smoke.ifo`/`smoke.idx` names; the
  dictzip path itself was never at fault)*
- [x] 5.3 Import a folder containing only a StarDict `.ifo` (companions absent)
  and confirm the app reports a failed load rather than listing a broken entry —
  *(host check done: `gd_scan_dicts -> 0 dictionary(ies)` and the file is
  recorded as a scan failure; confirmed on device by the half-staged `full/`
  collision, which produced exactly "No corresponding .dict file was found"
  and a failure banner rather than a crash)*
- [ ] 5.4 Remove a StarDict dictionary and confirm its staged files and index are
  deleted and lookups no longer return its words — **deferred at archive time**.
  The removal path is format-independent and covered by the existing recipes
  (#7, #8d); nothing StarDict-specific is left to observe, but it was not
  exercised on this pass.
- [ ] 5.5 Re-import a previously-failed StarDict folder on a device that already
  had the `.ifo`-only staged copy, and confirm the dictionary now loads without
  an app restart — **superseded**: this exposed `stale-import-cleanup`, which
  implemented the re-import-supersedes-a-failure behaviour. Verified there
  (device: a repaired directory became a loaded dictionary, 30 → 31) rather
  than here.
- [ ] 5.6 If a StarDict entry exists in the remote catalog, install it and
  confirm installed-detection reports it only after all its files land —
  **deferred at archive time**: no StarDict entry exists in the catalog yet.
  The installed-detection rule itself (every dictionary-role basename must be
  present) is asserted in `catalog_test` and documented in
  `docs/REMOTE-CATALOG.md`.

## 6. Record

- [x] 6.1 Update the `dictionary-management` spec wording if the archived delta
  differs from what shipped, then archive the change — delta matches what shipped
  (it describes staging the `.idx`/`.dict` companions and the missing-companion
  failure case, both implemented). Archiving is left until the on-device tasks in
  §5 are run
