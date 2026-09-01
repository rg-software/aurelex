## Context

Dictionaries are appended to the carve's in-memory list (`EngineState::dictionaries`)
by `gd_scan_dicts` and referenced by index from groups (`GroupDef::dictIndices`),
the article maker, and FTS. There is no way to drop one. Removal therefore has
to reconcile the same index-based references the boundary already manages
(`gd_move_dict` already shows the pattern: mutate the vector, then
`rebuildGroups()` to re-materialize `Instances::Group`s + `ArticleMaker`, both of
which hold the dictionary vector *by reference*).

See proposal.md — Why/What for motivation and scope.

## Goals / Non-Goals

**Goals**
- A loaded dictionary can be removed and disappears from list, groups, lookups, and FTS.
- Confirmation before the destructive step.
- Re-adding a removed dictionary works (scan dedup must not block it).

**Non-Goals**
- Deleting source files or the on-disk staged copies / indexes (the staged
  folder is shared; "remove" only unloads from the running app).
- Persisting the removal across engine restarts (scan on startup only re-loads
  from the staged folder; a removed dict returns on the next cold scan — see
  Risks).

## Decisions

### D1: `gd_remove_dict( int dict_index )` in the boundary
Follows the existing `gd_move_dict` pattern: erase `g_state->dictionaries[i]`,
drop `i` from every `GroupDef::dictIndices` (remap indices > i down by one),
then `rebuildGroups()`. Returns `0` on success, `-1` for an out-of-range index or
uninitialized engine. The removed `sptr` is released when the vector shrinks;
`ArticleMaker` is rebuilt so its by-reference group/dict vectors stay consistent.

### D2: Removal is engine-session-only; re-add is a fresh scan
Removal does not touch disk. A follow-up `gd_scan_dicts` of the same folder
re-adds the dictionary because the dedup set was built from *loaded* ids and the
removed id is no longer present. The "Re-add after removal" spec scenario falls
out of the existing dedup (fix in full-text-search session). If the app is
restarted, a cold scan re-loads everything from the staged folder, so a removed
dictionary reappears — acceptable for v1 (no persistent "removed" set; see
Risks).

### D3: IPC as a plain int opcode
`nativeRemoveDict(index)` in JNI + `OP_REMOVE_DICT` in `EngineService` /
`EngineClient.removeDict(index): Future<Int>`, mirroring `moveDict`. No new
payload shape.

### D4: UI — Remove button + confirmation on Dictionaries screen
Each dictionary row in `DictionariesScreen` gains a **Remove** action alongside
the existing ↑/↓ reorder. Tapping shows a confirm dialog; on confirm,
`viewModel.removeDict(index)` runs the engine call and refreshes dictionaries,
groups, and FTS index states (so a removed dict's FTS status row disappears).

## Risks / Trade-offs

- [Removal is not persisted: engine restart (or re-scan) brings the dictionary
  back from the staged folder.] → Mitigation: accepted for v1; matches the
  "load folder" mental model. A persistent "hidden dictionaries" set is a
  possible later improvement (tracked, not in scope).
- [Indices shift on removal; stale calls with an old index could hit the wrong
  dictionary.] → Mitigation: the UI refreshes the list immediately after a
  successful removal, and all removal/reorder flows re-read the current list.
- [Removing from every group is O(groups×dicts), trivial at v1 sizes.] →
  No mitigation needed.
- [Scanning loads **all** supported dictionaries in the picked folder, not a
  user-chosen subset.] → Current v1 limitation (known): the folder picker
  stages+scans every `.mdx`/`.dsl`/`.dsl.dz`/`.ifo` present, so "adding" a
  folder brings in everything it contains. Removing a single dict works
  (this change), but there is no per-file multi-select. Mitigation: per-file
  selection is a plausible later improvement (tracked, not in scope).
- [Dictionary count is stale after dedup/removal ("Dictionaries (N loaded)").]
  → Fixed as part of removal: the UI count is now derived from the actual
  loaded list (`refreshDictionaries`), not from an accumulated `+= n`.

## Migration Plan

No on-disk schema changes. Rollback = revert the boundary + UI; existing staged
dictionaries and indexes are untouched by removal.

## Open Questions

None — the one affordance boundary (persistence of removal) is explicitly
decided in D2/Risks.