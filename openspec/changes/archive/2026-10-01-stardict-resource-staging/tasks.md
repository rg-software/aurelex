## 1. Scope the recognition

- [x] 1.1 Add a pre-scan to the staging entry point that lists each picked folder
  for `*.ifo` files and records the StarDict basenames present, so a `res`
  directory can be attributed to a dictionary rather than matched by name alone
  — `AurelexActivity.folderHasStarDictIfo` lists the folder's children once and
  returns whether any `.ifo` is present; only the presence is needed for the
  `res/` rule (no basename set).
- [x] 1.2 Thread those basenames through `stageTreeInto` alongside the existing
  `inResourceDir` state — realized as a per-folder `stardictIfoInParent`
  boolean computed from the pre-scan, passed into the child-recursion decision.
- [x] 1.3 Decide the resource-directory rule: a directory named `res` is a
  resource tree only when its parent folder carries a StarDict `.ifo` (see
  `design.md`, "recognise `res` only as a sibling of a StarDict dictionary")
- [x] 1.4 Rename or re-document `isResourceDirName`, whose current name means
  "DSL resource tree" and would now be narrower than its behaviour — renamed to
  `isDslResourceDirName`, with a new `isStardictResDirName` (both documented).

## 2. Stage the directory form

- [x] 2.1 Have the walk treat a recognised `res` directory like a DSL `.files`
  tree: recurse and copy **everything** inside, bypassing the supported-dictionary
  filter
- [x] 2.2 Confirm the copied resources land at `<staged>/<sourceId>/res/<name>`,
  which is where `stardict.cc:1631` looks relative to the dictionary — the walk
  preserves the relative path; verified against the real factbook (`gd_get_resource`
  returned the 10310-byte `af_large_locator.gif`).
- [x] 2.3 Exempt resource files from `hasStagedCopy` dedup, as DSL `.files`
  contents already are, so a repeated image (flags recur) is not skipped — the
  existing `resource = inResourceDir` path already does this; `res` children now
  set `inResourceDir`.
- [x] 2.4 Confirm resource files do **not** enter the dictionary's id — the
  engine hashes its source paths, and resources must not change that (a second
  entry for the same dictionary would be the visible symptom). The engine's
  `makeDictionaryId` takes only idx/dict/syn/res-archive, never `res/` contents;
  no app change.
- Note: a `res.zip`/`<base>.res.zip` **does** join the engine's id inputs
  (`stardict.cc:1911`), so adding it yields the correct id for that packaging.

## 3. Stage the archive forms

- [x] 3.1 Add `res.zip` and the `<base>.res.zip` form to the supported-name
  filter (Java) so a dictionary shipping its resources as an archive is staged
  — `isStardictResourceArchiveName`.
- [x] 3.2 Mirror them in `kDictionaryExtensions` (C++) if catalog entries should
  be able to declare them; keep the two lists in step, as the companion fix
  established — added `.res.zip` to the table and the bare `res.zip` exact form
  to the matcher (its lack of a leading dot rules out `endsWith`).
- [x] 3.3 Confirm the engine finds a staged `res.zip` at the path it tries
  (`stardict.cc:1911`) — verified on host: with `res/` replaced by `res.zip`,
  `gd_get_resource("bres://…/af_large_locator.gif")` still returned 10310 bytes.

## 4. Automated coverage

- [x] 4.1 Extend the host classification test (`catalog_test` /
  `StagedCleanupTest` family) to cover the new archive names, and that an
  unrelated `res` directory is **not** treated as a resource tree when no `.ifo`
  is present — archive names in `catalog_test`; the `res` scoping rule in the new
  `app/StagingRules.hpp` (+ `StagingRulesTest.cpp`), which mirrors the Java walk
  (the SAF importer is not host-runnable).
- [x] 4.2 Build and run the host test targets; confirm the new assertions fail
  before the change and pass after — all 7 host tests pass. Before: `res.zip`/
  `word.res.zip` had no table entry (rejected) and `isResourceDirName` had no
  `res` branch, so the "unrelated `res`" check could not exist.
- [x] 4.3 Decide whether a StarDict resource fixture belongs in
  `scripts/make-smoke-stardict.py` — **decided no.** The smoke tool feeds the
  engine a complete directory and so bypasses the importer, which is the half this
  change fixes; and the engine's own `res/` reading is upstream (Aurelex changes
  no engine code). The engine half is instead pinned by a real dictionary:
  factbook's `res/` **and** `res.zip` both return the 10310-byte
  `af_large_locator.gif` on host (see Notes). A generated fixture would also test
  the code we wrote rather than the promise. Revisit only if an engine bump is
  suspected of regressing StarDict resources.

## 5. Documentation

- [x] 5.1 `docs/TESTING.md`: a recipe importing a real StarDict dictionary with
  a `res/` tree and confirming an article image renders — rows 8h (image renders)
  and 8i (unrelated `res/` not staged).
- [x] 5.2 `docs/REMOTE-CATALOG.md`: state the resource forms a StarDict entry may
  declare, if 3.2 admits them — `res.zip`/`<base>.res.zip` listed in the supported
  extensions and a "StarDict resources" subsection added.
- [x] 5.3 Confirm the README's StarDict "Works" claim is now true as written; the
  plan is to fix rather than to narrow the claim — true; row now names `res/`,
  and the import steps mention it.
- [ ] 5.4 Update the archived `dictionary-management` delta, then archive

## 6. Verify against a real dictionary

- [x] 6.1 On host, import **The World Factbook 2014** (`factbook.zip`, 2577
  headwords, 824 `res/*.gif`) through the smoke tool with its `res/` tree present
  and confirm `gd_get_resource` returns the image bytes — done: lookup of
  "Afghanistan Geography" returned `gd_get_resource("bres://…/af_large_locator.gif")
  -> 10310 bytes` (the reference measurement).
- [x] 6.2 Re-run the importer simulation over the factbook tree and confirm the
  count flips from *4 staged / 824 dropped* to *828 staged / 0 dropped* — done:
  OLD rule staged=4 dropped=824; NEW rule staged=828 dropped=0; the scoping guard
  left an unrelated `res/` unstaged.
- [ ] 6.3 On device, import the factbook folder and confirm an article's flag or
  map image renders in the WebView
- [x] 6.4 On device, re-import a StarDict dictionary imported before this change
  and confirm the resources now appear without an app restart — done with
  `isolated-dz` (a dictzip StarDict staged before this change): after adding its
  `res/` and re-importing, `files/staged/862e6fff/res/dot.gif` appeared and a
  lookup served it. This is what exposed the re-import data-loss bug — see
  section 7.
- [ ] 6.5 Confirm a folder containing a `res/` but no StarDict `.ifo` stages no
  `res/` contents (the scoping guard holds on real input)

## 7. Re-import safety (defect found while verifying 6.4)

- [x] 7.1 Characterise the data-loss bug: `StagingService.stageOne` staged into
  `staging-tmp/<id>` with `files/staged` as the dedup root, then deleted
  `files/staged/<id>` and renamed the temp over it. Unchanged files were deduped
  against the folder's own previous copy, so the swap deleted them. Confirmed on
  device: re-importing `isolated-dz` with `res/` added logged `deduped=3` and left
  only `res/dot.gif`; a second re-import (old copy gone) restored the files.
- [x] 7.2 Fix: overlay the temp tree onto the final dir (move each file into
  place, replacing a same-named file) instead of replacing the dir; keep the
  unchanged-re-import fast path.
- [x] 7.3 Host test: **not added.** The overlay is Android `java.io.File` logic in
  `StagingService` with no host harness (as with the importer itself); a C++
  mirror would test a copy, not the code. The device re-import (7.4) is the
  verification, matching the existing Java-side testing story.
- [x] 7.4 Re-verify on device: re-import a StarDict folder with `res/` added and
  confirm the dictionary files and the resource are both present afterwards —
  done: with the fix, re-importing `isolated-dz` after adding `res/extra.gif`
  logged `deduped=3 copied=2` and left `files/staged/862e6fff/` holding
  `dzsample.{ifo,idx,dict.dz}` **and** `res/{dot,extra}.gif` (before the fix the
  same re-import left only `res/`)..

## Notes

The measurement that motivates this change is reproducible and worth keeping:

- factbook `.ifo`: `sametypesequence=h`, `wordcount=2577`, `synwordcount=267`.
  It exercises HTML article bodies, a `.syn` file, a `.dict.dz`, and a `res/`
  tree — all four of which the generated smoke fixture lacks.
- Importer simulation before the fix: `would stage: 4, would DROP: 824`.
  After: `staged=828, dropped=0` (simulation over `factbook.zip`).
- Engine side, host smoke tool:
  - `res/` directory form: `gd_get_resource("bres://…/af_large_locator.gif")
    -> 10310 bytes`.
  - `res.zip` archive form: same lookup, `-> 10310 bytes` (with `res/` removed).
  The engine's dict id changes between the two packagings, as `stardict.cc:1911`
  folds the archive into `makeDictionaryId`.
