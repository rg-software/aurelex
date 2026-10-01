## Why

A StarDict dictionary keeps the images its articles reference in a sibling
resource folder, conventionally named `res/`. The engine reads them from there
(`engine/src/dict/stardict.cc:1631`), but the importer does not copy that folder:
`isResourceDirName` recognises only DSL's `<name>.files` tree, so a StarDict
`res/` directory's contents fall through to the supported-dictionary filter and
every image is dropped.

Measured on a real dictionary (The World Factbook 2014, 2577 headwords):
**4 files staged, 824 images dropped.** The dictionary loads and its text
renders, but every flag, map and locator image in it is missing. The README
claims StarDict "Works"; for any dictionary that carries images — which is the
normal case, since `res/` is the convention — it does not.

This was found only after the companion-file fix shipped: the fixture used to
verify that change was generated from the code under test and had no resources,
so it could not have caught this. A real dictionary did, immediately.

## What Changes

- The importer recognises a StarDict dictionary's resource locations and stages
  them, so the images its articles reference are present after import.
- The engine accepts three locations (`stardict.cc:1631`, `:1911`): a `res/`
  **directory**, a `res.zip` beside the dictionary, and a `<base>.res.zip`. The
  import SHALL cover what the engine can actually read, so a dictionary is not
  left half-imported depending on which packaging its author chose.
- The bundled `res/` case follows the existing DSL `<name>.files` precedent:
  copy the tree wholesale, because its contents are arbitrary assets (images,
  sounds) that no extension filter can enumerate.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: the folder-scanning requirement enumerates what is
  stage-copied per format. It currently names DSL's `<name>.files` tree as the
  only resource bundle; it must also name a StarDict dictionary's resource
  locations, with a scenario covering an imported StarDict dictionary whose
  article images resolve.

## Impact

- `app/android/src/org/aurelex/pocket/dictionary/AurelexActivity.java` —
  `isResourceDirName` (and the staging walk that consults it) and
  `isSupportedDictionaryName` for the archive forms.
- `app/RemoteCatalog.cpp` / `.hpp` — `kDictionaryExtensions`, if the `res.zip`
  forms are admitted for catalog entries; must stay in step with the Java list as
  before.
- `app/android/src/org/aurelex/pocket/dictionary/StagingService.java` — the
  temp→final step becomes an overlay (see `design.md`), because staging the
  `res/` tree exposes a re-import data-loss bug: unchanged files are deduped
  against the folder's own previous copy and were then deleted with it.
- `app/StagingRules.hpp` (+ `app/tests/StagingRulesTest.cpp`) — the host-tested
  mirror of the resource-directory rule the Java walk applies.
- `docs/TESTING.md` — a recipe importing a real StarDict dictionary and checking
  an article image renders.
- `README.md` — the StarDict row's claim can stand as "Works" once this lands.
- No engine, carve, boundary or patch change: the engine already reads all three
  locations; the app is the only side dropping them.

## Risks

- **Staging cost.** A `res/` tree can be large (the factbook case is 824 files,
  ~11 MB) and is copied wholesale, like a DSL `.files` tree. Acceptable: it is
  the dictionary's own content and the user picked the folder deliberately.
- **A `res/` folder belonging to something else.** A directory named `res` is a
  common name. Matching it anywhere in a picked tree could copy unrelated files.
  Treatments must stay scoped to a directory that sits beside a StarDict
  dictionary, not to any `res` in the tree — see `design.md`.
- **The dedup interaction found during the companion fix.** Files are deduped by
  name+size+mtime across the stage root, so a resource file identical to one
  already staged elsewhere is skipped. That is correct for dictionary files and
  must not be allowed to drop a resource the engine will look for — also
  addressed in `design.md`.
