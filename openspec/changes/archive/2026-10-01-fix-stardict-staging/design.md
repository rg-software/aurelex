## Context

See `proposal.md` — Why. Two facts from the current tree shape this design:

- The engine's StarDict reader resolves a dictionary's companions by basename,
  trying a fixed set of spellings (`engine/src/dict/stardict.cc:1723-1735`):
  - index: `idx`, `idx.gz`, `idx.dz` (and upper-case forms)
  - definitions: `dict`, `dict.dz` (and upper-case forms) — note there is **no**
    `dict.gz`; the compressed form is dictzip only
  - synonyms: `syn`, `syn.gz`, `syn.dz` (and upper-case forms), used only when
    the `.ifo` declares `synwordcount`

  Missing index or definitions are hard failures (`exNoIdxFile`,
  `exNoDictFile`); a missing `.syn` is tolerated.
- The staging filter and the catalog's format list are the **same knowledge
  duplicated in two languages**: `AurelexActivity.isSupportedDictionaryName`
  (Java, drives what is copied) and `kDictionaryExtensions` (C++, drives catalog
  install validation and installed-detection).

The engine path is already proven: `carve/CMakeLists.txt` compiles `stardict.cc`,
and `scripts/make-smoke-stardict.py` + `carve/smoke/main.cpp:314` index and search
a StarDict fixture in CI. The smoke tool feeds the engine a complete directory,
so it never exercises the staging filter — which is why this bug survived a
green CI.

## Goals / Non-Goals

**Goals:**

- A StarDict dictionary picked through the SAF picker is staged with everything
  the engine needs to open it.
- The catalog's format classification agrees, so a StarDict catalog entry can be
  declared and installed with its companions.
- Automated coverage that fails if the classification stops accepting a complete
  StarDict set.

**Non-Goals:**

- Unifying the Java and C++ lists into one source of truth. Worth doing
  eventually; not worth a cross-language build step for this fix.
- Wiring up XDXF (compiled but unexposed) or any format that is not already
  read successfully today.
- Changing the engine, the carve, or the patch set. None is involved.

## Decisions

### Decision: extension-based matching, not a basename-sibling rule

The staging walker is a single-pass streaming recursion that decides per entry
as it goes (`AurelexActivity.stageTreeInto`). A basename-sibling rule ("copy
`word.idx` only because `word.ifo` exists") would need the set of `.ifo`
basenames known before files are decided, i.e. a second pass or a pre-scan.

Chosen: add the companion extensions to the same list the walker already
consults.

**Alternatives considered:**

- *Pre-scan for `.ifo` basenames, then stage by basename.* More precise, but
  adds a full extra tree walk per pick and a second code path to keep correct.
- *Treat the StarDict family like the DSL `.files` tree* (a wholesale-copy
  directory rule). Doesn't fit: StarDict companions are siblings of the `.ifo`
  in the picked folder, not a subdirectory, so there is no directory boundary to
  key on.

### Decision: mirror the engine's resolution set exactly

The added suffixes are exactly the lower-cased set the reader tries:

```
.idx  .idx.gz  .idx.dz
.dict .dict.dz
.syn  .syn.gz  .syn.dz
```

Deliberately **not** a blanket `.gz`/`.dz` or a bare `.idx`/`.dict` guess: the
set is derived from the reader, and it preserves the reader's asymmetry (no
`.dict.gz`).

**Alternatives considered:**

- *`.idx`, `.dict`, `.syn` only.* Would silently fail for a dictzip'd or
  gzipped dictionary — a real and common StarDict packaging.
- *Match any `.dz`/`.gz`.* Would sweep unrelated archives into staged storage.

### Decision: update both lists, cross-reference them in comments

`kDictionaryExtensions` gains the same suffixes so the catalog agrees with
staging. Because the two lists must stay identical and live in different
languages, each gets a comment naming the other as its twin and the reason.

### Decision: test the C++ classification; verify staging on device

The Java filter has no host test harness. `catalog_test` already links
`RemoteCatalog.cpp`, so `isSupportedDictionaryName` can be asserted directly
there (accepts a complete StarDict set and each compressed variant; still rejects
`.bgl`, `.xdxf`, `.slob`). The staging half is verified on a device by importing
a folder with a real StarDict dictionary.

## Risks / Trade-offs

- **[Over-copy]** A bare `.idx`/`.dict` in a picked folder is staged even with no
  `.ifo` present. → Benign: the engine only load-discovers `.ifo` primaries, so
  stray files are inert; the cost is a few wasted bytes. Accepted in exchange for
  a single-pass walker.
- **[List drift]** The Java and C++ lists can diverge again. → Comment
  cross-reference plus a C++ test on the C++ side. The Java side remains covered
  only by device verification; noted rather than solved.
- **[Fixed data already staged]** A user who imported a StarDict dictionary
  before this fix has an `.ifo` with no companions in app storage, and a rescan
  will not repair it. → They must re-import the folder (see Migration Plan).
- **[`syn` with no `synwordcount`]** A `.syn` file may be staged for a dictionary
  whose `.ifo` does not declare it. → The reader already ignores `.syn` in that
  case (`stardict.cc:1945-1946`), so this is inert.

## Migration Plan

No data migration is possible or needed: the fix changes what is *copied*, not
what is stored. A previously-failed StarDict import left only a `.ifo` in
`files/staged/`, and the companions were never copied, so there is nothing to
recover on disk. Users re-import the folder to pick the dictionary up; the
staged `.ifo` is replaced in place and the existing re-import path
(`gd_scan_dicts`' source-change reload) rebuilds it.

Rollback is reverting the two lists; no stored state depends on the change.

## Open Questions

- Whether to collapse the duplicated extension knowledge into one generated
  source. Deferrable: it does not affect the specs, the approach, or the task
  breakdown, and the current duplication is small.
