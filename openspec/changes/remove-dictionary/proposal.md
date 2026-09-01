## Why

A user can add dictionaries (by picking a folder, optionally several times) but
cannot remove one once added. The only destructive action today is deleting a
whole **group**; an individual loaded dictionary stays in the list (and in every
group, in FTS, and in lookups) forever, and repeated picks accumulate junk. The
user needs a way to drop an unneeded dictionary from the loaded set.

## What Changes

- **Boundary C API:** add `gd_remove_dict( int dict_index )` to drop a loaded
  dictionary. It removes the dictionary's entry from the global loaded set and
  from every group (including the implicit "All"), then rebuilds the article
  maker so future lookups/lists reflect the removal. `0` on success, `-1` on an
  invalid index. (Pure boundary change — the engine's `Dictionary` objects are
  owned by the carve and can be released here; no upstream edit.)
- **Android IPC:** add `nativeRemoveDict` (JNI) + `OP_REMOVE_DICT` and the
  matching `EngineClient.removeDict(index)` future, mirroring `moveDict`.
- **UI:** add a **Remove** action on the Dictionaries screen (next to each
  dictionary's existing ↑/↓ reorder), with a confirm step since it is
  destructive. Removing a dictionary updates the list, the groups list, and
  FTS.
- **Dedup (already fixed):** this change also keeps the scan-time dedup
  (re-adding the same folder does not duplicate) so that removal + re-add is
  the intended lifecycle and repeated picks stay clean.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `dictionary-management`: add a requirement that a loaded dictionary can be
  removed from the app's loaded set, and that removal is reflected across
  groups, lookups, and full-text search.

## Impact

- `app/src/main/cpp/engine/goldendict.h` + `gd_boundary.cc` — `gd_remove_dict`.
- `app/src/main/cpp/jni/jni_bridge.cc` — `nativeRemoveDict`.
- `NativeEngine.kt`, `EngineService.kt`, `EngineClient.kt` — `OP_REMOVE_DICT`.
- `MainViewModel` + `MainActivity.kt` (`DictionariesScreen`) — remove action +
  state refresh.
- Smoke (`smoke/main.cpp`) asserts removal shrinks `gd_dict_count` and a removed
  dictionary no longer resolves in a lookup.
