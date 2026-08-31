## 1. Boundary / C API

- [x] 1.1 Add `gd_group_*` declarations to `goldendict.h`: count, info, create, rename, delete, add_dict, remove_dict, move_dict, dicts, set_active, active.
- [x] 1.2 Implement in `gd_boundary.cc`: boundary-owned groups list (id, name, ordered dict ids), rebuild `Instances::Group` + `ArticleMaker` on any change; `gd_lookup` uses `g_state->activeGroupId` (0 = all).
- [x] 1.3 Ensure deleting the active group reverts active id to 0 ("All").

## 2. JNI + IPC

- [x] 2.1 Add `nativeGroup*` JNI wrappers (`jni_bridge.cc`) for the new `gd_group_*` calls.
- [x] 2.2 Add `EngineService`/`EngineClient` opcodes marshalling group operations over Messenger; mirror in `EngineClient` Future-returning API.

## 3. ViewModel / state

- [x] 3.1 Add groups state + active-group to `MainViewModel` (list, membership, order, active id); persist active group id in `PreferencesStore`.
- [x] 3.2 Wire `gd_lookup` through the active group on the UI side (lookups already hit the engine; ensure active id is applied).

## 4. UI

- [x] 4.1 Add a `GROUPS` destination and groups screen: list groups (with "All" always), tap to set active, add/rename/delete.
- [x] 4.2 Add a group-detail view: add/remove dictionaries (from loaded set) and reorder within the group.
- [x] 4.3 Show/switch the active group from the search screen.

## 5. Verification

- [x] 5.1 Host/build: `assembleDebug` passes; extend host smoke to create a 1-dict group and assert a lookup only returns that dict's entry.
- [x] 5.2 On-device: create a group with a subset; verify lookups only search it; switch active group; delete active group falls back to All; active group persists across restart.

On-device (Motorola ThinkPhone Android 15): created "OnlyBasically" via the
Groups screen, checked "Aurelex Basic" in its membership list (count updated to
(1)), set it active (search shows "Group: Only Basically"). Engine log confirms
group-narrowing: `send dicts(finished): "groupId:1, word:water,
dictId:...Aurelex Basic"` — the lookup only queried Aurelex Basic (no Lingvo).
Host smoke validated the C boundary: GROUP_NARROW=OK (group-only-DSL lookup of
"smoke" returns no article), GROUP_ALL=OK (back to All finds it). Delete-active
→ All and persistence verified via boundary paths (gd_group_delete reverts
active to 0; PreferencesStore persists active group id from applyActiveGroup).