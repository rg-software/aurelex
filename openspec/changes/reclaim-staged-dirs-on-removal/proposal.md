## Why

Removing a dictionary leaves most of its staged files on disk. Measured on
device against a StarDict dictionary (The World Factbook, `.ifo` + `.idx` +
`.dict.dz` + `.syn` + a `res/` tree of 824 images):

| After removal | State |
| --- | --- |
| primary file `stardict.ifo` | **deleted** |
| `stardict.idx`, `.dict.dz`, `.syn` | **left behind** |
| `res/` (824 images) | **left behind** |
| staged directory itself | **left behind** |
| index + `_FTS_x` entries | correctly deleted |

About **18 MB** is orphaned per removal, and nothing ever reclaims it:
`sweepStaleStagedDirs()` only reclaims a directory the scan reported as
**failed**, and a directory whose primary file is gone produces neither a
dictionary nor a failure.

The device log shows the sharing guard refusing the directory delete:

```
removed staged source file ".../staged/70549544/stardict.ifo" ok= true
staged dir kept, a loaded dictionary uses it ".../staged/70549544"
```

at a moment when only two dictionaries remained loaded and both were in
**different** directories. The guard is meant to protect a directory shared by
several dictionaries; here it protects one that nothing uses.

The requirement already says removal deletes "its staged copy". It does not.

### Scope is probably not StarDict-only

The affected shape is "a primary file plus sibling files a dictionary needs",
which is how several formats are staged:

- **StarDict** — `.ifo` + `.idx` + `.dict.dz` + `.syn` + `res/`
- **DSL** — `.dsl.dz` + `<name>.dsl.files/`
- **MDict** — `.mdx` + `.mdd` + loose assets

So this is likely to reproduce for every format, and any fix must be verified
against more than the StarDict case that exposed it.

## What Changes

- **A removed dictionary's staged directory is actually reclaimed** when no
  other loaded dictionary still reads from it — the sharing guard stops
  misjudging a directory that has just been emptied of its owner.
- **No orphan is left unreclaimable.** A staged directory that holds no primary
  file at all currently has no owner; it must be reclaimable rather than
  accumulating forever. This also cleans up directories already leaked.
- **Sibling safety is preserved.** One import folder can hold several
  dictionaries; removing one must still not delete a directory another still
  uses. That guard exists for a good reason and must keep working — a regression
  here would delete a working dictionary's files.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: the "Remove a loaded dictionary" requirement already
  promises removal deletes the dictionary's staged copy. This change makes that
  true and adds scenarios for the non-primary files and the leftover directory,
  so a partial delete cannot be considered acceptable again.

## Impact

- `app/EngineController.cpp` — `deleteIdentityFiles` / `removeStagedDirIfUnused`
  / `liveDictionarySources`, and `sweepStaleStagedDirs`.
- `app/StagedCleanup.hpp` — the sharing predicate (header-only, host-testable).
- `app/tests/StagedCleanupTest.cpp` — a regression test for the case that failed.
- No engine, boundary, QML, or staging-format change.
