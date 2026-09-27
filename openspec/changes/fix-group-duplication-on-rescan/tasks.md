## 1. Root cause

- [x] 1.1 Confirm `loadGroupsLocked()` is the only reader of `groups.json` and that `gd_scan_dicts` calls it on every scan, so the reload path is shared by app start and every subsequent import
- [x] 1.2 Confirm it clears `allOrder` but not `groupDefs`, which is what makes a second scan append a second copy of every group
- [x] 1.3 Confirm the duplicate is not cosmetic: `gd_group_delete` erases only the first id match (so the duplicate is undeletable), `saveGroupsLocked` persists the duplicate, and `rebuildGroups` materializes both into `Instances::Group`s sharing one id

## 2. Fix - make the reload a reload

- [x] 2.1 Clear `g_state->groupDefs` in `loadGroupsLocked()` before populating it, so a scan is idempotent for the group set. This is what the function's own comment already claimed
- [x] 2.2 Keep `groups.json` as the single source of truth (every `gd_group_*` mutation writes it synchronously, so a reload cannot lose in-memory state) and note that reasoning at the clear
- [x] 2.3 Do not add a boundary function or change any `gd_*` signature - the whole fix is inside `loadGroupsLocked`

## 3. Self-heal for devices already hit by the bug

- [x] 3.1 While loading, collapse entries that share an id into the first one and union their `dictIndices`, so a `groups.json` already written with a repeated id repairs itself
- [x] 3.2 Write the repaired file back (`saveGroupsLocked`) only when a repair actually happened, so the fix is durable and the normal scan path still does no extra I/O
- [x] 3.3 Log whether a repair occurred, next to the existing `groups loaded: %d user groups` line, so the repair is visible in logcat

## 4. Regression guard

- [x] 4.1 Add a `GROUP_RESCAN=OK|FAIL` smoke assertion: create a group, re-scan the same folder, and require `gd_group_count()` to be unchanged
- [x] 4.2 Add a `GROUP_ID_STABLE=OK|FAIL` assertion: the created group must still resolve through `gd_group_info` to the same id and name after the re-scan (catches a duplicated id as well as a dropped group)
- [x] 4.3 Add a `GROUP_RELOAD_SOURCE=OK|FAIL` assertion that pins the mechanism 4.1 cannot: the smoke rewrites the stored group name in `groups.json`, re-scans, and requires the new name to surface. A loader that appends keeps the previous in-memory copy, so this is the assertion that actually fails on the defect - verified by reverting the fix (4.1/4.2 pass, 4.3 fails, exit 1)
- [x] 4.4 Fold all three into the smoke tool's exit code so a local run fails, not just CI
- [x] 4.5 Add the matching `grep` gates to `.github/workflows/engine-smoke.yml`
- [x] 4.6 Run the host smoke build locally and confirm the assertions pass
- [x] 4.7 Verify the self-heal on a hand-corrupted `groups.json` (two entries sharing one id, different members): the first scan collapses them to one group holding the union of the members and rewrites the file, so the repair is durable

## 5. On-device verification

- [ ] 5.1 With a dictionary in a group, import a newer build of the same dictionary, let it index, and confirm the Groups list still shows one row for that group
- [ ] 5.2 On a device that already accumulated duplicates, launch the app and confirm the duplicates collapse to one group with the union of their members, and that the stored group set is clean afterwards (next scan logs no repair)
