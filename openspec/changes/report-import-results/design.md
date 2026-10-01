## Context

See proposal.md — Why. The relevant current state:

**The banner is a `Rectangle` + `ColumnLayout` + `Repeater`** in the Dictionaries
pane, `implicitHeight: failuresCol.implicitHeight + 12` and `Layout.fillHeight:
false`, sitting above a `ListView` at `Layout.fillHeight: true`
(`main.qml:1712-1792`). Every row is a `RowLayout` with an eliding basename and a
28dp trash glyph whose `MouseArea` calls `engine.removeScanFailure()`.

**That glyph deletes.** `removeScanFailure()` → `stagedAncestor()` →
`removeStagedDirIfUnused()` → `QDir::removeRecursively()`
(`EngineController.cpp:993-1086`). The row is dropped from the list because the
directory went away, not instead of it.

**Automatic cleanup already exists, at directory granularity.**
`sweepStaleStagedDirs()` runs after every scan (called from `runScan()` at line
435) and deletes a staged directory when no loaded dictionary uses it *and* a scan
reported a failure under it. So a corrupt dictionary alone in its own folder is
already cleaned up automatically — the banner is the fallback.

**The fallback cannot fire in the case it exists for.**
`removeStagedDirIfUnused()` bails out when `StagedCleanup::isUsedByLoadedDictionary()`
is true (`EngineController.cpp:1077-1080`). One corrupt file in a folder of twenty
means nineteen loaded dictionaries share that folder, so the sweep skips it and the
trash refuses — logged as *"failed import left in place (shared or refused)"*. The
file is reported, on disk, and unreachable through the UI.

**The model is `QVariantList` of `{file}`, and it is consume-on-read.**
`gd_scan_failures()` clears `lastScanFailures` as it hands them over
(`carve/gd_boundary.cc:656`), so the banner is a one-shot by construction.

**The delete path is guarded, and the guards are worth keeping.**
`StagedCleanup.hpp` decides containment (`isDirectChildOf`) and sharing in one
place so no caller can apply one guard and forget the other. That separation is
deliberate and must survive this change.

## Goals / Non-Goals

**Goals:**

- The banner reports; it does not act. Nothing in it deletes.
- Everything the import failed on is gone by the time the banner appears, so there
  is nothing for the user to clean up by hand.
- Any number of results is readable without hiding the dictionary list.
- Everything actionable is resolvable in the Dictionaries list, which is where
  selection and confirmation already exist.

**Non-Goals:**

- A new navigation surface. A tab is somewhere you *go*; this is a report about a
  batch that just finished, and after it the app is in a consistent state with
  nothing left broken.
- A persistent, browsable import history.
- A summary modal. Dismissed too early it is information the user has to
  memorize, and it would duplicate the banner rather than replace it.
- Deleting anything the user asked for. Automatic deletion is confined to sources
  the engine reported as unloadable.

## Decisions

### D1: Automatic deletion, scoped to the failing file set

The user is right that a corrupt or unreadable source has no value: it cannot
become valid, it cannot be repaired, and keeping it only means the engine retries
it on every scan. So the system deletes it, and says so.

The delete is scoped to **the failing source's own files**, not to the directory.
This is what fixes the shared-folder bug (Context): the failing dictionary's file
set comes from the boundary's identity call, so deleting it is correct even when
its siblings loaded. `StagedCleanup` then reclaims the directory only when nothing
loaded remains in it, which preserves the sibling case.

This is the one place the app deletes without a user action, and it is bounded to
files the engine itself declared unloadable. Nothing that loaded is ever touched,
and no dictionary the user asked for is removed.

### D2: The banner carries no destructive control

With D1, every row the banner can describe refers to files that are already gone
or were never installed. A control labelled "remove" on such a row would be
either a no-op or a second, redundant path to the same deletion — and in the
shared-folder case it is exactly the control that currently silently fails.

So the trash glyph goes away and is replaced by **one dismiss control for the
whole banner**. Dismissal is pure UI state: it removes the banner and changes
nothing else, which is what makes it safe to make the whole banner
informational.

*Alternative considered:* a per-row dismiss. Rejected — it implies each row is
individually actionable, which is precisely the implication to remove.

### D3: One dismiss control, and a new import clears stale results

The banner describes a batch. Two things end it: the user dismisses it, or the
user starts another import, which supersedes it. The second is not a nicety — a
banner that has accumulated a clash from last week next to a fresh failure is
reporting on a batch that is no longer the most recent one, which is how a report
stops being trustworthy.

Implementation: clear the model at the start of a pick, before the new results are
collected, rather than trying to merge or age rows.

### D4: Rows name the dictionary, not the file

The current row shows `modelData.file.replace(/^.*[\\/]/, "")` — a basename inside
an opaque `staged/<hash>/` directory. It is unreadable, and it is worst precisely
in the cases this change is about: a duplicate or a clash *has* a dictionary name,
and the name is what the user recognises.

The model becomes `{name, file, reason}`. Where a dictionary name exists, the row
shows it; a file name is a fallback for sources that never loaded and so have no
name. The `reason` is what makes the three outcomes distinguishable, because the
remedies differ and the old wording collapsed them:

| reason | files | what the user does, if anything |
|---|---|---|
| could not be loaded | deleted (D1) | nothing |
| already present, not added again | incoming copy deleted | nothing |
| a different dictionary of this name is installed | incoming copy deleted | remove the installed one, re-import |

The third row must not inherit the old banner's advice — *"Remove it and import
the folder again"* (`main.qml:1786`) is untrue for a clash, where the folder is
already added and the fix is elsewhere.

### D5: Bounded height with internal scrolling

`implicitHeight` on an unbounded `Repeater` grows with the failure count and
consumes the `ColumnLayout`, starving the `ListView` below it — so a bad import can
hide the dictionary list entirely, which is the opposite of what the user needs
when the banner is telling them about two identically-named dictionaries.

The banner's height becomes `min(contentHeight, cap)` with the rows in a
`ListView`/`Flickable` that scrolls within that bound, and the headline keeps the
count visible via a placeholder-substituted message ("Parameterized messages"
already requires the placeholder form). The list below keeps `Layout.fillHeight:
true` and therefore its space at any result count.

*Alternative considered:* a modal summary. Rejected — see the goal it fails: a
modal the user swipes away is a report they must memorize, and the user's framing
is that the banner is a place to return to.

*Alternative considered:* a separate tab. Rejected — nothing here is worth
navigating to, and the dock is already full.

### D6: The accessible-name contract changes shape, not existence

`"Remove failed import"` is documented in `AGENTS.md`'s accessible-element table
and is the hook UIAutomator uses. Since the control changes from a per-row delete
to a single dismiss, that entry changes to a dismiss name (e.g. `"Dismiss import
results"`) and `AGENTS.md` is updated in the same change, along with any test that
addresses the old name.

`localization`'s existing "Accessibility test identifiers remain invariant" already
requires exactly this, so no localization delta is needed — see the proposal.

### D7: The report stays transient, because nothing is left to fix

There is no standing condition needing a permanent home. Broken files are deleted;
skipped and rejected copies are deleted; the installed dictionaries are untouched
and consistent. A clash leaves the app in a valid state — the old build is
installed and works — and the only residue is the user's knowledge that a newer
build exists, which the banner states and which they may act on or ignore. Hence
no persistent screen, and the banner is not re-raised on later scans.

## Risks / Trade-offs

- **A user who ignores the banner may believe an import fully succeeded.**
  → Every row states what was not added and why, and a new import clears stale
  rows so what is on screen always describes the latest batch. This is the direct
  cost of not prompting mid-batch, accepted in `resolve-duplicate-dictionaries`.

- **Deleting without asking is irreversible.** → Confined to sources the engine
  reported as unloadable, which cannot become valid. Covered by a spec scenario
  asserting no successfully-loaded dictionary loses a file.

- **Losing the per-row trash loses a cleanup path for a stranded directory** — one
  no scan reported and no dictionary uses. → The existing sweep handles reported
  failures; this state is out of scope. The dismiss still clears the banner, so the
  app is never left showing stale information.

- **A bounded banner can hide rows behind a scroll**, which is a small regression
  against "everything visible at once". → The count is always in the headline, so
  a user knows there is more than they can see, and the rows are one tap away.

- **The consume-on-read failure list means the report is assembled from a single
  scan's failures.** → Unchanged; the model already holds what was reported, and
  `sweepStaleStagedDirs` runs before the model is read into QML.

## Migration Plan

1. Extend the report model to `{name, file, reason}` and populate `reason` for the
   three outcomes. The banner still renders, now with names.
2. Add automatic deletion of an unloadable source's file set (D1), replacing the
   sweep's whole-directory behaviour for the shared-folder case. The sweep stays
   for the directory-reclamation step.
3. Bound the banner's height and move its rows into a scrolling list (D5).
4. Replace the per-row trash with a single dismiss, clear the model on a new pick
  (D3), and update `AGENTS.md` plus any affected test (D6).
5. Translate the new and changed strings (`scripts/update-translations.ps1`, the
   `values-ru/` + `values-ja/` resources, and the recompiled `.qm` catalogs).

Each step is independently shippable; none depends on a carve change.

## Open Questions

None.
