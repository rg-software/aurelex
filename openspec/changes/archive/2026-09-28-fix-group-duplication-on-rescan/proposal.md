## Why

Importing a new version of a dictionary duplicates every user group.

`loadGroupsLocked()` (`carve/gd_boundary.cc`) is the only reader of `groups.json`,
and `gd_scan_dicts` calls it at the end of **every** scan. It cleared `allOrder`
but appended to `g_state->groupDefs` without clearing it, so a second scan in the
same process left the already-loaded groups in place and pushed a second copy of
every persisted group on top of them.

Reproducing the reported case: a dictionary `Kaikki` sits in a group `Kaikki`.
Adding a newer build of that dictionary stages a new file (new path, so a new
dictionary id), which ends the staging marker and triggers `runScan()` →
`gd_scan_dicts` → `loadGroupsLocked` → `groupDefs` becomes
`[{id:1,"Kaikki"}, {id:1,"Kaikki"}]`. `gd_group_count()` then reports 3 and the
Groups tab shows `All`, `Kaikki`, `Kaikki`.

The damage compounds and the duplicate is a dead end:

- The next mutation rewrites `groups.json` from `groupDefs`, so the duplicate id
  is now **persisted** and survives a restart.
- `gd_group_delete` erases only the *first* entry with a matching id, so deleting
  `Kaikki` removes one copy and leaves the other. The user cannot get back to a
  single group through the UI.
- The stale copy is not inert: `rebuildGroups` materializes both into
  `Instances::Group`s with the same id, so `ArticleMaker` and `gd_suggest`
  (which resolve a group by id) can no longer tell which `Kaikki` is meant.

Every dictionary import, and every app start, made this worse. The reported
"new MD5/size" detail is not itself the trigger — any second scan is; the new
version is just the ordinary reason a user rescans.

## What Changes

- `loadGroupsLocked()` clears `groupDefs` before loading, matching the "reload
  (not append)" intent its own comment already claimed. `groups.json` is the
  source of truth (every group mutation writes it synchronously), so reloading
  is lossless and makes a scan idempotent.
- Loading is also **self-healing**: a `groups.json` that already holds a repeated
  id (written while the bug was live) is collapsed to one group per id, keeping
  the union of the membership, and the repaired file is written back so the
  repair is durable. Users who already hit the bug recover on the next scan with
  no manual config edit.
- Three smoke assertions, with matching CI gates. Two pin the user-visible
  invariant (group count and group identity survive a re-scan). The third pins
  the mechanism: the smoke rewrites the stored group name, re-scans, and
  requires the new name to surface - which is the only check that fails on the
  append itself, because the self-heal already hides the duplicate count.

No engine change: `engine/` stays byte-for-byte at the pinned tag, no
`patches/` entry, no upstream delta. Boundary work only.

## Capabilities

### Modified Capabilities
- `dictionary-management`: the "Dictionary groups" requirement gains the invariant
  that a dictionary scan is idempotent for the group set — a scan SHALL NOT add
  groups, and a stored group set that already contains a repeated identifier
  SHALL be repaired to one group per identifier.

## Impact

- Affected code:
  - `carve/gd_boundary.cc` — `loadGroupsLocked()`.
  - `carve/smoke/main.cpp` — `GROUP_RESCAN` / `GROUP_ID_STABLE` /
    `GROUP_RELOAD_SOURCE` assertions in the existing groups block, folded into
    the tool's exit code, plus a `rewriteGroupName` helper that edits
    `groups.json` in place.
  - `.github/workflows/engine-smoke.yml` — the three matching `grep` gates.
- Affected APIs: none. No `gd_*` boundary function is added, removed, or
  changed; the bug and the fix are both inside `loadGroupsLocked`.
- Affected dependencies: none. No new engine source, no patch, no upstream bump.
- Upstream fidelity: `engine/` unchanged.
- Localization: no catalogs touched. No user-visible English text changes (the
  duplicate group rows are the bug being removed, not new copy), so
  `scripts/update-translations.ps1` is not needed.
