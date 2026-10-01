## 1. Scope the recognition

- [ ] 1.1 Add a pre-scan to the staging entry point that lists each picked folder
  for `*.ifo` files and records the StarDict basenames present, so a `res`
  directory can be attributed to a dictionary rather than matched by name alone
- [ ] 1.2 Thread those basenames through `stageTreeInto` alongside the existing
  `inResourceDir` state
- [ ] 1.3 Decide the resource-directory rule: a directory named `res` is a
  resource tree only when its parent folder carries a StarDict `.ifo` (see
  `design.md`, "recognise `res` only as a sibling of a StarDict dictionary")
- [ ] 1.4 Rename or re-document `isResourceDirName`, whose current name means
  "DSL resource tree" and would now be narrower than its behaviour

## 2. Stage the directory form

- [ ] 2.1 Have the walk treat a recognised `res` directory like a DSL `.files`
  tree: recurse and copy **everything** inside, bypassing the supported-dictionary
  filter
- [ ] 2.2 Confirm the copied resources land at `<staged>/<sourceId>/res/<name>`,
  which is where `stardict.cc:1631` looks relative to the dictionary
- [ ] 2.3 Exempt resource files from `hasStagedCopy` dedup, as DSL `.files`
  contents already are, so a repeated image (flags recur) is not skipped
- [ ] 2.4 Confirm resource files do **not** enter the dictionary's id — the
  engine hashes its source paths, and resources must not change that (a second
  entry for the same dictionary would be the visible symptom)

## 3. Stage the archive forms

- [ ] 3.1 Add `res.zip` and the `<base>.res.zip` form to the supported-name
  filter (Java) so a dictionary shipping its resources as an archive is staged
- [ ] 3.2 Mirror them in `kDictionaryExtensions` (C++) if catalog entries should
  be able to declare them; keep the two lists in step, as the companion fix
  established
- [ ] 3.3 Confirm the engine finds a staged `res.zip` at the path it tries
  (`stardict.cc:1911`)

## 4. Automated coverage

- [ ] 4.1 Extend the host classification test (`catalog_test` /
  `StagedCleanupTest` family) to cover the new archive names, and that an
  unrelated `res` directory is **not** treated as a resource tree when no `.ifo`
  is present
- [ ] 4.2 Build and run the host test targets; confirm the new assertions fail
  before the change and pass after
- [ ] 4.3 Decide whether a StarDict resource fixture belongs in
  `scripts/make-smoke-stardict.py`; if so, add a `res/` tree and an image
  reference to its article so the engine path is exercised in CI. The smoke tool
  feeds the engine a complete directory and therefore bypasses the importer, so
  state clearly which half this covers

## 5. Documentation

- [ ] 5.1 `docs/TESTING.md`: a recipe importing a real StarDict dictionary with
  a `res/` tree and confirming an article image renders
- [ ] 5.2 `docs/REMOTE-CATALOG.md`: state the resource forms a StarDict entry may
  declare, if 3.2 admits them
- [ ] 5.3 Confirm the README's StarDict "Works" claim is now true as written; the
  plan is to fix rather than to narrow the claim
- [ ] 5.4 Update the archived `dictionary-management` delta, then archive

## 6. Verify against a real dictionary

- [ ] 6.1 On host, import **The World Factbook 2014** (`factbook.zip`, 2577
  headwords, 824 `res/*.gif`) through the smoke tool with its `res/` tree present
  and confirm `gd_get_resource` returns the image bytes — the 10310-byte
  `af_large_locator.gif` is the reference measurement (an earlier run returned 0
  bytes because the tree was incomplete; that was the test, not the engine)
- [ ] 6.2 Re-run the importer simulation over the factbook tree and confirm the
  count flips from *4 staged / 824 dropped* to *828 staged / 0 dropped*
- [ ] 6.3 On device, import the factbook folder and confirm an article's flag or
  map image renders in the WebView
- [ ] 6.4 On device, re-import a StarDict dictionary imported before this change
  and confirm the resources now appear without an app restart
- [ ] 6.5 Confirm a folder containing a `res/` but no StarDict `.ifo` stages no
  `res/` contents (the scoping guard holds on real input)

## Notes

The measurement that motivates this change is reproducible and worth keeping:

- factbook `.ifo`: `sametypesequence=h`, `wordcount=2577`, `synwordcount=267`.
  It exercises HTML article bodies, a `.syn` file, a `.dict.dz`, and a `res/`
  tree — all four of which the generated smoke fixture lacks.
- Importer simulation before the fix: `would stage: 4, would DROP: 824`.
