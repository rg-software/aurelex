## Context

See `proposal.md` — Why. Three facts from the current code shape this:

- The engine reads StarDict resources from **three** places
  (`engine/src/dict/stardict.cc`):
  - `:1631` — `<dictionary folder>/res/<name>`, a directory;
  - `:1911` — `res.zip`, `<base>.res.zip`, or `res/res.zip` beside the
    dictionary. These are also added to the dictionary's id inputs, so their
    presence is part of what identifies the dictionary.
- The importer stages three kinds of thing today
  (`AurelexActivity.stageTreeInto`): supported dictionary files by extension;
  everything inside a directory named `<something>.files` (the DSL convention,
  via `isResourceDirName`); and the `.files.zip` archive form.
- The walk decides **per entry as it goes**, and passes `inResourceDir` down the
  recursion. A resource tree is therefore recognised by the *directory name*
  alone, with no knowledge of which dictionary it belongs to.

## Goals / Non-Goals

**Goals:**

- A StarDict dictionary imported through the picker has the resources its
  articles reference, from whichever of the three locations it ships.
- Recognition is scoped so an unrelated `res/` in a large picked tree is not
  captured as a dictionary's resources.
- The behaviour is verifiable against a real dictionary, not only a generated
  fixture.

**Non-Goals:**

- Changing the engine, carve, boundary, or patch set. The engine already reads
  all three locations; only the app drops them.
- Handling a `res/` tree that is **shared** by several dictionaries in one folder
  (see Decisions — it is copied per dictionary, which is the safe direction).
- Copying resources declared some other way (a dictionary that references images
  by URL, say). Out of scope; StarDict's convention is the folder or the zip.

## Decisions

### Decision: recognise `res` only as a sibling of a StarDict dictionary

A bare `isResourceDirName(name)` extension match on `res` would copy **any**
folder named `res` anywhere in the picked tree — a common name, and in a large
tree that could pull in unrelated megabytes.

The walker already threads state down the recursion; it needs the set of
StarDict basenames present in a directory to decide. Two shapes are possible:

- **A pre-scan**: list the folder once for `*.ifo`, note their basenames, then
  stage. Costs one extra listing per folder, and is exact.
- **Order-independent acceptance inside the walk**: accept a `res` directory when
  the *current* folder also contains a `.ifo` — but a walker may descend into
  `res` before seeing the `.ifo`, and file order is not guaranteed.

Chosen: **the pre-scan**, because correctness here does not depend on iteration
order, and the cost is one directory listing, not a second full copy.

**Alternatives considered:** *Accept any `res` directory.* Simplest, but the
false-positive cost is unbounded and silent — the user's storage grows with files
that will never resolve.

### Decision: copy a `res/` tree wholesale, like a DSL `.files` tree

The contents are arbitrary assets (`.gif`, `.png`, `.wav`, anything the article
references), so no extension filter can enumerate them. This mirrors the existing
DSL `<name>.files` handling exactly, including exempting the contents from the
supported-dictionary filter.

### Decision: stage the archive forms by extension

`res.zip` and `<base>.res.zip` are ordinary files with a known extension, so they
join the supported-name filter rather than needing a directory rule. `res.zip` is
ambiguous in the same way `res/` is — but the cost differs: the engine tries
`res.zip` first, and a stray one that belongs to nothing is a single file the
engine ignores, whereas a stray `res/` tree is many files. Matching those by
extension is therefore an acceptable trade; matching the directory was not.

### Decision: keep the resource files out of the dedup and id paths

Two hazards already met while fixing the companion files:

- **Dedup.** `hasStagedCopy` skips a file whose name+size+mtime matches one
  already staged elsewhere, to stop an intersecting pick duplicating a
  dictionary. Resource files must be exempt, as DSL `.files` contents already
  are, or a repeated image (flags recur across dictionaries) could be skipped and
  leave a dictionary missing a resource the engine will look for.
- **Identity.** Resource files must not enter the dictionary's id, which is an
  MD5 over its source paths. DSL resources are already excluded from it; the
  StarDict case must be too, or adding resources would produce a second entry for
  the same dictionary.

## Risks / Trade-offs

- **[Unrelated `res/`]** Still possible if a folder genuinely contains both a
  StarDict `.ifo` and an unrelated `res/`. → Accepted: in that layout the `res/`
  is far more likely to be the dictionary's; the alternative (never copying it)
  is the bug being fixed.
- **[Storage]** A `res/` tree is copied per dictionary; a folder holding several
  StarDict dictionaries that share one `res/` would duplicate it. → Accepted for
  now: duplication wastes space, whereas *not* copying breaks the articles. Noted
  as a non-goal rather than solved.
- **[Large trees]** The factbook case is 824 files, ~11 MB. Copying is bounded by
  what the user picked.
- **[The `isResourceDirName` name]** It currently means "DSL resource tree".
  Adding `res` makes the name narrower than the behaviour; the tasks rename or
  document it so the next reader is not misled.

## Migration Plan

No stored state changes. A StarDict dictionary already imported without its
resources stays without them until re-imported — the staged copy holds no `res/`,
so nothing can be recovered in place, and re-importing the folder replaces it.
Task 7.x covers re-importing an existing StarDict dictionary to confirm.

## Open Questions

None. The three engine locations are known, the scoping rule is decided, and the
verification path (a real dictionary) exists.
