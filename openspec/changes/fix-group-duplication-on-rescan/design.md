# Design - fix group duplication on re-scan

## D1 - The stored group set is the source of truth, and a scan replaces it

`groups.json` is written synchronously by every group mutation
(`gd_group_create`, `gd_group_rename`, `gd_group_delete`, `gd_group_add_dict`,
`gd_group_remove_dict`, `gd_group_move_dict`, `gd_group_set_active` - each ends
in `rebuildGroups(); saveGroupsLocked();`). There is no in-memory-only group
state that the file does not already hold, and no code path writes group state
somewhere else. So a reload from the file is lossless, and
`loadGroupsLocked()` must *replace* `groupDefs` rather than append to it.

`loadGroupsLocked()` is called from exactly one place, the tail of
`gd_scan_dicts`, which runs on app start and after every import (the staging
marker clearing triggers `runScan()`). So the reload is on the hot path of the
single most frequent user action in the app, and it has to be idempotent.

Decision: clear `groupDefs` alongside `allOrder` at the top of the load.

Rejected: making the group set append-only in memory and diffing against the
file. That keeps two representations of the same thing and re-introduces the
class of bug rather than removing it.

Rejected: loading groups only from `gd_init` and never on a scan. Membership is
stored as dictionary ids and can only be resolved to indices once dictionaries
are loaded, so the load genuinely has to happen after the scan. The bug is not
that the load happens there; it is that the load did not reset.

## D2 - Self-heal a repeated id by unioning members, then persist

A device that ran the buggy build has a `groups.json` holding the same id more
than once (the next mutation persisted the in-memory duplicate). Repairing only
on a future append would never fire for those users - the file is already
corrupt when it is read.

Decision: while loading, an entry whose id is already present is merged into the
first entry with that id, unioning `dictIndices` and keeping the first entry's
name. Union rather than replace because the duplicates came from the same group
being loaded twice, so their memberships are the same set in practice; unioning
is the choice that cannot lose a member if they ever differ. Keeping the first
name is arbitrary but harmless - the names are identical in every file the bug
produced, and inventing a rename would be a surprising side effect of a scan.

If any merge happened, `saveGroupsLocked()` writes the file back, so the repair
is durable instead of being redone on every scan. Gated on the repair flag so
the ordinary path still does no extra I/O.

Dropping the duplicate silently would also stop the symptom, but it would lose
membership for any file where the two entries disagree, so union is preferred.

## D3 - The regression guard must pin the mechanism, not the symptom

The natural smoke assertion - "re-scan, group count unchanged" - does **not**
fail on the buggy loader once D2 exists: the append happens, then the self-heal
collapses the repeat, and the count is right. Verified locally by reverting the
`groupDefs.clear()` line with the heal left in: `GROUP_RESCAN` and
`GROUP_ID_STABLE` both still pass.

What distinguishes "reload replaced the set" from "reload merged into the set" is
what the loader does with a *changed* stored group. A merge keeps the previous
in-memory `GroupDef` and only folds in the new members, so a renamed group in
the file stays under its old name in the app.

Decision: the smoke rewrites a group's name in `groups.json` directly, re-scans,
and asserts the new name comes back (`GROUP_RELOAD_SOURCE`). The boundary exposes
no API for editing the file behind the API's back, so the smoke helper does it
with a literal `"name":"<old>"` substitution against the compact JSON the
boundary writes. Verified: with the fix reverted, `GROUP_RESCAN=OK` and
`GROUP_ID_STABLE=OK` pass while `GROUP_RELOAD_SOURCE=FAIL` and the tool exits 1.

Rejected: a unit test of `loadGroupsLocked` in isolation. It would need the
engine state and a dictionary set to resolve ids against, which is most of what
the smoke tool already sets up, and the carve has no separate test target.

## D4 - No boundary or engine surface change

The defect and the fix are both inside one static function in an anonymous
namespace. No `gd_*` signature moves, no `patches/` entry, no upstream delta, so
`engine/` stays byte-for-byte at the pinned tag and the merge contract in
`AGENTS.md` is untouched. The app side needs nothing: it already re-reads the
group list after every scan (`EngineController::runScan` -> `refreshGroups()`),
so it picks up both the fix and the self-heal with no QML or controller edit.

## Risks

- **Losing a group on load.** If `groups.json` were ever stale relative to
  in-memory state, clearing before loading would drop live edits. D1 rules this
  out: there is no unsaved mutation path.
- **Heal choosing a name.** D2 keeps the first entry's name, which is
  unobservable for files the bug produced. A hand-edited file with one id and two
  different names would keep the first - acceptable, and the alternative
  (renaming on scan) is worse.
- **`nextGroupId` after a heal.** The heal never drops an id, so the persisted
  `nextGroupId` stays above every loaded id and a later `gd_group_create` cannot
  collide. Verified in the hand-corrupted run: `nextGroupId` advanced to 3 past
  the repaired id 1 and the new id 2.
