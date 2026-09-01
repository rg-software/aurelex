## 1. Boundary C API

- [ ] 1.1 Declare `gd_remove_dict( int dict_index )` in `goldendict.h`
      (0 success, -1 invalid index / not initialized).
- [ ] 1.2 Implement `gd_remove_dict` in `gd_boundary.cc`: erase the dictionary,
      drop its index from every `GroupDef::dictIndices` (remapping indices > it
      down by one), and `rebuildGroups()`.

## 2. Android IPC

- [ ] 2.1 Add `nativeRemoveDict` to `jni_bridge.cc` + `NativeEngine.kt`.
- [ ] 2.2 Add `OP_REMOVE_DICT` to `EngineService.kt` + `EngineClient.kt`
      (`removeDict(index): Future<Int>`, mirroring `moveDict`).

## 3. ViewModel + UI

- [ ] 3.1 Add `removeDict(dictIndex)` to `MainViewModel`: call the engine,
      refresh `_dictionaries`, `_groups`, and `_ftsIndexStates`.
- [ ] 3.2 Add a **Remove** action + confirmation dialog to
      `DictionariesScreen` in `MainActivity.kt` (alongside the ↑/↓ reorder).

## 4. Verification (host + device)

- [ ] 4.1 Host smoke: after scanning the fixture set, `gd_remove_dict(1)` then
      assert `gd_dict_count` drops by one, the removed dictionary's headword no
      longer resolves in a lookup, and a re-`gd_scan_dicts` re-adds it.
- [ ] 4.2 CI `engine-smoke.yml`: add the removal assertion to the smoke gate.
- [ ] 4.3 On-device (Motorola ThinkPhone): remove a dictionary, confirm it
      disappears from the list, groups, and FTS results; confirm re-adding the
      same folder brings it back without duplicates.