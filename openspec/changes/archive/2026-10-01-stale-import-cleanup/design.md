## Context

See `proposal.md` — Why. Two facts shape the approach:

- **`gd_scan_failures` already returns the failing file's full path**
  (`carve/gd_boundary.cc:646`), and `EngineController::collectScanFailures`
  turns each line into `{ "file": <path> }` in `m_scanFailures`. The path is
  therefore enough to act on: no boundary or engine change is needed.
- **A staged import directory is named by a deterministic hash of the picked
  folder's URI** (`StagingService.java:138`:
  `Integer.toHexString(treeUri.toString().hashCode())`), and staging writes to
  `files/staging-tmp/<id>` then atomically renames to `files/staged/<id>`.

That second fact is what makes the re-import half tractable, and it is also why
the current advice fails. Re-importing the same folder targets the **same**
`<sourceId>`, so it *does* replace that directory — but only when staging
succeeds. In the observed failure the re-import was a *different* fixture folder
and therefore a different id, leaving the broken directory untouched. More
importantly, a re-import that stages successfully still only replaces its own
`<sourceId>`; it never sweeps a half-staged directory left by an earlier pick of
a *different* folder, and it does not clear the failure list.

The existing removal path already contains the guard this must not regress:
`deleteDictionaryFiles` (`EngineController.cpp:984-1033`) deletes an index entry,
the dictionary's own staged file, and the staged directory **only when no other
loaded dictionary uses it** — a single import folder may hold several
dictionaries. Cleanup must reuse that reasoning rather than remove directories
eagerly.

## Goals / Non-Goals

**Goals:**

- A reported load failure is removable from the UI, and removal actually frees
  the staged files.
- Re-importing a folder that previously failed leaves no stale copy behind, so
  the documented remedy works.
- The banner's copy matches what the app does.
- No loaded dictionary and no sibling dictionary in a shared import folder is
  ever deleted by this path.

**Non-Goals:**

- Diagnosing *why* a file failed (corrupt vs truncated vs unsupported) — the
  report stays "this file could not be loaded".
- Auto-deleting failures. Removal is user-initiated only; a transient failure
  must not silently destroy an import.
- Any change to the engine, carve, boundary or patch set.

## Decisions

### Decision: act on the failing file's path, guarded by the staged root

Removal takes the `file` path from the failure report, resolves it against the
staged root with the existing `stagedAncestor` helper
(`EngineController.cpp:1054`), and refuses anything that does not resolve inside
the staged root. A path from the engine is trusted for reporting but not for
deleting: containment is checked before any filesystem call.

**Alternatives considered:** *Key failures by `sourceId` instead of path.* The
id is not currently carried through the failure report and would need a boundary
change to obtain; the path is already there and human-readable in the banner.

### Decision: one cleanup routine, shared by both defects

Both defects want the same operation — "delete this import's staged directory if
nothing loaded still needs it". Implemented once, taking a staged directory,
then:

- the banner's remove action calls it for the directory containing the reported
  file;
- the re-import sweep calls it for a directory that is present but from which no
  dictionary loaded.

**Alternatives considered:** *Give the banner an action and separately make
re-import wipe the id directory.* Two code paths for one outcome invites the
guard being applied in one and forgotten in the other — exactly the class of
mistake this whole change exists to fix.

### Decision: re-import cleanup happens after a successful scan, not at staging

The sweep runs after the scan completes, because only then is it known which
staged directories produced loaded dictionaries. Sweeping earlier would race the
scan and could delete files the engine is opening.

### Decision: the banner exposes a remove action rather than a dismiss

A plain dismiss would clear the message while leaving the untouchable files and
the recurring failure — the state the user is already stuck in. The action
performs the cleanup.

**Alternatives considered:** *Auto-clear the banner when the file disappears.*
Still needed (a sweep should not leave a stale message), but it is a consequence
of the fix, not a substitute: if the user cannot delete the file, clearing the
message just hides the problem.

### Decision: keep the sweep to directories with no loaded dictionary

The sweep considers only staged directories that contributed **zero** loaded
dictionaries. A directory with even one loaded dictionary is left alone
entirely, so a shared import folder keeps its working members and the existing
per-file removal remains the way to drop one member.

## Risks / Trade-offs

- **[Deleting a sibling]** The sweep removes a whole directory when nothing
  loaded from it. If a future format produces a dictionary whose primary file is
  recognised later than the scan, a directory could look empty and be removed. →
  The sweep only ever runs on directories the scan reported as failed, and never
  on a directory that yielded a dictionary in the same scan.
- **[A failure that is not stale]** A file can fail for a reason that a re-import
  fixes (an interrupted copy). Removing on request is still correct, but the
  sweep must not pre-empt the user: it runs only after a re-import of the same
  folder, and only for a directory that produced nothing.
- **[Persisted failure state]** `m_scanFailures` is in-memory and rebuilt per
  scan, so there is no stored state to migrate and nothing stale after an
  upgrade. The reported failure of an already-broken directory will reappear once
  on the first scan after this ships, and the new action removes it.
- **[Path containment]** A bug here deletes user data. → The staged-root
  containment check is the single gate, and the tasks call for an explicit test
  that a path outside the staged root is refused.

## Migration Plan

No stored state changes and nothing to migrate: staged directories and the
failure list are both reconstructed at run time. Rollback is reverting the
commit. A user carrying an already-unremovable failed import gets the new action
on their next scan and can clear it.
