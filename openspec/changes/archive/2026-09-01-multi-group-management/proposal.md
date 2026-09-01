## Why

Aurelex currently treats all loaded dictionaries as one unfiltered set: lookups always run across everything. Users with mixed dictionaries (e.g. an EN dictionary plus a cycling/enthusiast RU pack) want to search a chosen subset in a chosen order. goldendict's engine already has full group support (a group is a named, ordered subset); v1 just never surfaced it. This milestone exposes group CRUD + active-group selection in the UI through a thin boundary extension.

## What Changes

- **Groups model**: users can create, rename, and delete named groups of dictionaries; each group is an ordered subset (dictionaries can be added/removed and reordered within a group).
- **Active group**: one group is active for lookups; searching uses only that group's dictionaries, in that group's order. An "All" group (all dictionaries) is implicit and always available.
- **Boundary extension**: the `gd_*` C API gains group operations (list/create/rename/delete groups, set membership/order per group, set/get the active group), and `gd_lookup` uses the active group. Engine `ArticleMaker` already filters by group id, so this is a thin seam.
- **UI**: a groups screen listing groups (with per-group dictionary membership and order), a way to set the active group, and the search screen reflects the active group.

## Capabilities

### New Capabilities

- `groups`: managing named groups of dictionaries — CRUD, per-group dictionary membership and order, and selecting which group is active for lookups.

### Modified Capabilities

- `lookup`: a lookup uses the **active group's** dictionaries and order (instead of always all dictionaries); the combined article reflects that group.
- `dictionary-management`: the existing single-group reorder is superseded by the groups model (the "All" group carries the global order).

## Impact

- Boundary (`app/src/main/cpp/engine/gd_boundary.cc` + `goldendict.h`): new `gd_group_*` functions; `gd_lookup` honours the active group. Engine `ArticleMaker`/`Instances::Group` already support this — no upstream change needed.
- JNI bridge (`app/src/main/cpp/jni/jni_bridge.cc`) + `EngineClient`/`EngineService`: marshal group operations over Messenger IPC.
- Kotlin UI: groups screen, active-group selector, search screen integration.
- This touches the boundary (C API + IPC), so it goes through the normal apply flow, but requires no upstream `patches/` change.