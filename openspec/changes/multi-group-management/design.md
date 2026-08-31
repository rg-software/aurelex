## Context

The engine already has full group support internally: `Instances::Group`/`Groups` (id, name, ordered dict members), and `ArticleMaker::makeDefinitionFor(word, groupId, ...)` uses the group's dictionaries when a matching group is found, else all dictionaries. The current boundary keeps `g_state->groups` (empty) and calls `makeDefinitionFor(word, 0, ...)` so lookups always hit all dictionaries. See proposal.md — Why; specs for the behavioral contract.

## Goals / Non-Goals

**Goals:**
- Surface group CRUD + membership/order + active-group in the boundary (`gd_group_*`) and IPC, reusing the engine's existing group mechanics.
- Lookups use the active group.

**Non-Goals:**
- No engine/`patches/` change (ArticleMaker already group-aware).
- No group icons/hotkeys (desktop-only; v1 groups are plain named lists).

## Decisions

### D1. Group state lives in the boundary, not the engine config
The boundary maintains a small list of groups (id, name, ordered dict-ids) in `g_state`, rebuilding `Instances::Group` (which holds `sptr` to dictionaries) whenever dictionaries or group membership change. The engine's `ArticleMaker` already takes the group vector, so the boundary passes the active group's id into `gd_lookup`'s `makeDefinitionFor`.
- Alternative: persist groups into `Config` and let the engine load them — heavier and couples UI config to engine config; the boundary-owned model is simpler and keeps the merge tiny.

### D2. Group IDs and the implicit "All" group
Group ids are small integers assigned by the boundary. A reserved id (`0`) means "All" (every dictionary, in global dictionary order) and is always present; it cannot be deleted. `gd_lookup` passes the active group id (0 = all) to `makeDefinitionFor`. If the active group is deleted, the boundary reverts to 0.

### D3. Boundary API (`goldendict.h` additions)
Thin `gd_group_*` functions, all serialized by the existing engine mutex:
- `gd_group_count`, `gd_group_info(i, &id, name, &size)`
- `gd_group_create(name, &id)`, `gd_group_rename(id, name)`, `gd_group_delete(id)`
- `gd_group_add_dict(id, dictIndex)`, `gd_group_remove_dict(id, dictIndex)`, `gd_group_move_dict(id, from, to)`
- `gd_group_set_active(id)`, `gd_group_active(&id)`
`gd_lookup` switches to using `g_state->activeGroupId` instead of hardcoded `0`.

### D4. IPC: extend the existing Messenger protocol
`EngineClient`/`EngineService` gain opcodes wrapping the new `gd_group_*` calls, mirroring the existing pattern (one opcode per operation, reply via `msg.replyTo`).

### D5. UI: groups screen + active-group selector
A `GROUPS` destination lists groups (tap to set active, with an "All" entry always present); a group detail allows adding/removing dictionaries (checkboxes) and reordering. The search screen shows/lets you switch the active group. Building this reuses the existing back-stack navigation and `PreferencesStore` for the last-active group id (so it persists across restarts).

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| ArticleMaker holds `const ref` to the group vector; rebuilding it must keep references valid | Rebuild `ArticleMaker` (and its group vector) together whenever membership changes, same as current dict-scan rebuild |
| Deleting the active group leaves lookups broken | D2: revert active id to 0 ("All") on delete |
| Active-group persistence across restarts | Persist active group id in `PreferencesStore`, re-apply on load |

## Migration Plan

Greenfield — v1 never exposed groups, so no user data to migrate. Existing installs start with the implicit "All" group (current behavior) and an empty additional-groups list.

## Open Questions

- Should group membership changes be restricted to already-indexed dictionaries only? (Yes in practice — groups are built from loaded dictionaries; no new indexing implied.)