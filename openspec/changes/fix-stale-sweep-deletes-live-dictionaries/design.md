## Context

See `proposal.md` — Why, for the motivation. What matters for the approach:

The staged root is `files/staged/<sourceId>/`, one directory per import (see
`app/main.cpp:84-87`). Two facts about that layout drive everything here:

1. **Staging is recursive and preserves relative paths.** `AurelexActivity.stageTreeInto`
   recreates the picked tree's subfolder structure inside the staged directory
   (`app/android/.../AurelexActivity.java:588-597`, "Recurse into the subfolder,
   preserving the relative path"). So `Download/dicts/en/foo.mdx` stages to
   `staged/<sourceId>/en/foo.mdx`. The relative layout is load-bearing, not incidental:
   DSL resources live in a sibling `<dict>.files/`, StarDict in a sibling `res/`, and
   MDict loose assets beside the `.mdx` — all resolved relative to the dictionary.
2. **The carve's scan is recursive too** (`gd_scan_dicts` walks subdirectories), so a
   nested dictionary loads normally and appears in the dictionary list.

`EngineController::sweepStaleStagedDirs()` (`app/EngineController.cpp:1373`) therefore
reads facts 1 and 2 inconsistently. It lists `QDir::Files` at the **top level only**
(`:1415-1426`) to decide "holds no dictionary", so a directory whose dictionaries all
live one level down is classified as an orphan and handed to
`QDir::removeRecursively()` — while those dictionaries were loaded from it by the very
scan that ran immediately before.

The second defect is an ordering one. The sweep's in-use guard resolves through
`liveDictionarySources()` (`:1333`), which reads `m_dictionaries` — the QML-facing
model. That model is filled by `refreshDictionaries()`, which the scan chain calls
*after* the sweep (`:446` vs the sweep at `:443`). On a cold start `m_dictionaries` is
therefore empty at the moment the sweep runs, so `liveDictionarySources()` returns an
empty list and every directory looks unused. The guard is not merely weak on the first
scan; it is vacuous, and startup is exactly when the sweep is most dangerous.

## Goals / Non-Goals

**Goals**
- Make the orphan test agree with the recursive scan and the recursive staging.
- Give the sweep an in-use set that is authoritative for the scan it is deciding about.
- Reduce "may this directory be deleted" to one predicate, evaluated identically at
  every call site.
- Put that predicate where a host test can reach it.

**Non-Goals**
- Changing the on-disk staging layout. Flattening the tree would be the cheapest way to
  fix the top-level bug, and is rejected — see D1.
- Deciding whether an *unloadable* source may be deleted without asking. That is
  `report-import-results`' scope; this change only makes the current deletion safe
  (see D3 and Open Questions).
- Any carve, `gd_*` or engine change. Everything here is app-side, so no `patches/`
  entry and no CI smoke work.

## Decisions

### D1: Test the whole staged tree for a primary dictionary file

The orphan test becomes a recursive walk that short-circuits on the first match:
`QDir::entryInfoList(QDir::Files | QDir::Subdirectories | QDir::NoDotAndDotDot)`,
then `StagingRules::isPrimaryDictionaryName` per entry. `QDir::Subdirectories` makes
this one call rather than a hand-rolled `QDirIterator`.

*Alternative — flatten staging so primaries always land at the top level.* Rejected: it
changes the layout of every already-staged import and every existing directory would
have to be migrated, and it fights the format resource layouts that depend on a
dictionary sitting beside its own resources.

*Alternative — reuse the carve's recursive `collectFiles` through a `gd_*` call.* Rejected:
it takes `g_engineMutex` (see the `fetchIdentityInventory` comment at `:465-467` for why
that forces off-thread work), which reintroduces the ordering problem this change exists
to remove. A directory walk over a staged tree of a few thousand resource files is
microseconds and needs no lock.

The walk runs **after** the cheap string-prefix "is it in use" test, so a directory a
loaded dictionary reads from is never walked at all.

### D2: The sweep is handed the scan's own loaded-source set

The scan already knows, synchronously and off-thread, exactly which dictionaries the
engine loaded: its task runs `gd_scan_dicts()` and then `gd_dict_count()`
(`:412-418`). That task is extended to also read each loaded dictionary's source path
via `gd_dict_info()` and return them alongside the count. This is not new work — it is
the same read `refreshDictionaries()` performs milliseconds later (`:799-845`), just
taken at the point where the answer is authoritative instead of after the UI model has
caught up.

`sweepStaleStagedDirs()` takes that set as a parameter. It stops consulting
`liveDictionarySources()`.

The other callers — `removeScanFailure()` and `deleteDictionaryFiles()`, i.e. the
user-driven removal paths — keep using `liveDictionarySources()`, because there the
UI model *is* the right authority: it reflects an edit the user just made, including
the `m_unloadedSources` exclusions that stop a just-unloaded dictionary from keeping
its own directory alive. Two authorities, each used where it is correct, rather than
one authority that is correct in one place and silently vacuous in the other.

`removeStagedDirIfUnused()` gains the source set as an explicit parameter so the
containment/sharing gate cannot be applied by one caller and skipped by another —
the same reason `StagedCleanup::mayRemoveStagedDir` exists as a single shared gate.

### D3: The two false positives go; the failure branch is left alone

The sweep has two independent ways to reach `removeRecursively()`, and only one of them
is implicated in the reported incident:

- **The top-level-only orphan test** (D1) — fired with **no scan failures at all**. A
  nested import is misclassified as an orphan on its own. This is the proximate cause
  of the reported loss.
- **The reported-failure branch** (`:1437-1449`) — did not fire in the reported incident,
  because that update produced no new load errors. It is a separate defect and is
  **out of scope here** (see Non-Goals and Open Questions).

The orphan test therefore becomes recursive, and the guard becomes authoritative (D2).
Those two changes are what fix the incident.

They are also, incidentally, what makes the untouched failure branch safe: with a real
in-use set, a directory holding a loadable dictionary is no longer deletable through
*any* branch, so the "one corrupt file takes its nineteen siblings with it" hazard is
closed as a side effect of the guard fix rather than by touching that branch. The
branch's own policy — should an unloadable source be deleted unattended at all, and at
file-set rather than directory granularity — stays where `report-import-results` already
puts it. Nothing this change does depends on answering that question.

### D4: The predicate lives in a header, not in the controller

`hasPrimary`'s loop currently sits inline in `EngineController.cpp`, which is why the
regression shipped with no test: `StagingRulesTest.cpp` covers the *name* predicate
(`isPrimaryDictionaryName`) but nothing covers the top-level-only walk that applies it.
The walk joins `StagedCleanup.hpp` next to the containment and sharing gates, so
`StagedCleanupTest.cpp` covers nested, flat and empty directories on the host.

### D5: The two layers are independently necessary — do not remove the recursive test

It is tempting to conclude that D2's authoritative in-use set makes D1's recursive orphan
test redundant: if a loaded dictionary's source is known, the directory is "used" and is
skipped before the orphan test is ever reached. On the incident's own device that is true,
and D2 alone would have prevented the reported loss.

The recursive test is nonetheless load-bearing, for a concrete case:

`gd_dict_info()` (`carve/gd_boundary.cc:924`) returns `-1` when the source path does not fit
its `file_size` buffer, and the buffers here are the sizes this file has always used
(`char file[512]`). A dictionary staged at a path of 512 bytes or more is therefore loaded by
the engine but **absent from the in-use set** — `readDictInfoAt()` reports `ok = false` and
the scan drops it. For that dictionary the in-use guard protects nothing, and only
`holdsPrimaryDictionaryFile()` still sees the file on disk and keeps the directory.

So the layers are not belt-and-braces:

- the in-use set protects a dictionary the boundary can *name*;
- the recursive test protects a dictionary it *cannot*.

A future simplification that drops the recursive test on the grounds that the in-use set
already covers it would reintroduce live-data deletion for deep paths. The 512-byte buffer is
itself worth revisiting (see Open Questions), but until it is, the recursive test is the
only thing standing between a long path and `removeRecursively()`.

## Risks / Trade-offs

- **[A first-launch scan is now doing more work]** → The added `gd_dict_info()` reads are
  one boundary call per loaded dictionary (6 on the reference device), off-thread in the
  existing scan task. The recursive walk short-circuits and is skipped entirely for any
  directory already known to be in use.
- **[The recursive walk could be slow for a resource-heavy import]** → The reference
  device holds ~1000 resource files in one staged `res/`; a full walk is a few
  milliseconds. Note the walk still descends into resource trees to look for a primary.
  Bounded by staged-tree size, which the user controls by what they import.
- **[The orphan test gets looser, so genuinely-empty directories are reclaimed less
  eagerly]** → Only for directories holding a dictionary file in a subfolder, which is
  the intended correction. A directory with no primary anywhere is still reclaimed, so
  the disk-reclaim path that motivated the sweep keeps working.
- **[Users who already lost dictionaries get nothing back]** → Unrecoverable: the staged
  copies were the only copy the app owned and the originals live in the user's own
  folders. Worth an explicit line in the release notes rather than a silent fix.
- **[Attribution of the reported incident is inferred, not observed]** → The two defects
  explain the loss and neither requires a scan failure, but the affected device has not
  been inspected. See Open Questions.

## Migration Plan

No data migration, and no schema or layout change: on upgrade the sweep simply stops
mis-classifying nested imports. A user who re-imports the affected folder stages it
again and it stays.

Rollback is a pure revert — the change adds no persisted state, so there is nothing to
unwind.

## Open Questions

- **The boundary's fixed 512-byte path buffer is a latent defect, left as found.** A
  dictionary whose staged path is ≥512 bytes is loaded by the engine but is omitted from
  both the QML model (`refreshDictionaries()` skips `gd_dict_info() != 0`) and the sweep's
  in-use set, so it would be **invisible in the Dictionaries list** — a pre-existing
  usability bug, not a deletion risk, since D1's recursive test still protects the files
  (D5). Not fixed here — and the fix is cheaper than this note's first draft claimed, which is
  worth recording so the correction is not lost. `gd_dict_info` takes `file_size` from the
  **caller** and refuses only when `f.size() + 1 > file_size` (`gd_boundary.cc:924`), so the
  limit is the *app's own buffer*, not the boundary's. The two sites are `readDictInfoAt()`'s
  `char file[512]` and the FTS loop's `fb[512]` (`EngineController.cpp:422`, `:704`); the same
  test guards the name through `name[256]` (`gd_boundary.cc:916`). Raising them to `PATH_MAX`
  (4096) removes the defect with no boundary edit, no `patches/` entry and no engine
  involvement — `patches/` holds deviations from the pinned engine source only
  (`docs/ENGINE.md`), and `carve/` is not one. Note the comparison counts **bytes**, not
  characters: UTF-8 CJK/Russian folder names cost 2-3 bytes each, so the room left for a
  user's folder tree is ~447 bytes after the fixed prefix
  (`/data/user/0/<pkg>/files/staged/<sourceId>/` = 64 bytes), less than it looks for a
  non-Latin collection. The reference device's
  longest staged path is ~250 bytes, well inside the buffer; whether real users hit it
  depends on how deep their dictionary folders are. **Reproduced on device while verifying
  D5**, so the consequence is real rather than theoretical: a valid dictionary at a 530-byte
  path was loaded (it counted toward `gd_dict_count`) but was absent from both the in-use set
  and the Dictionaries list, while an otherwise identical copy at 500 bytes was named
  normally — confirming the boundary sits at 512 as read.
- **The reported-failure branch (`:1437-1449`) is left as found.** It did not fire in the
  incident. It is not *correct* — its evidence is per-file (`gd_boundary.cc:580/585/597`
  append only primaries) while its blast radius is a whole directory, which is the same
  category error `report-import-results` opens with, and it collides with
  `dictionary-management` §"Failures are not cleaned up without the user asking". Fixing
  it means deciding whether an unloadable source may be deleted unattended at file-set
  granularity; that decision belongs to `report-import-results`, which already proposes
  it. This change only guarantees the branch can no longer reach a directory holding a
  loadable dictionary. Deferrable in the strong sense: no task below depends on it, and
  the specs written here hold whichever way that change lands.
- ~~**Confirming the attribution on the affected device.**~~ **Closed — confirmed.** The
  reported device (Xiaomi 15, Android 16, Play install of v0.3.1 first launched
  2026-10-02 09:25) came back with `staged import folders: 0` and `gd_dict_count = 0`,
  and **every** dictionary file on its shared storage sits in a subfolder —
  `Download/dics/La-En Elementary Latin Dictionary (Lewis)/lat-eng_…dsl.dz`,
  `GoldenDict/English/American Heritage Dictionary (4th Ed)/En-En_…dsl.dz`. No folder
  the user could pick has a dictionary at its top level, so D1's top-level-only test
  classified every import as an orphan. The originals were untouched on the drive; only
  the staged copies were destroyed. No dictionary file anywhere on that device's
  `/sdcard` is flat, which is why nothing survived and why this will recur on re-import
  until the fix lands.