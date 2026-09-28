## 1. Root cause

- [x] 1.1 Confirm `refreshDictionaries` sorts the exposed list by name after reading it in engine order, so a display position is not the engine index (`app/EngineController.cpp:655-702`)
- [x] 1.2 Confirm `removeDictionary` passed its argument straight to `gd_dict_id`/`gd_remove_dict`, which index `g_state->dictionaries` (`carve/gd_boundary.cc:907`, `:977`)
- [x] 1.3 Confirm on device (29 loaded dictionaries): selecting "Aurelex Basic (DZ)" and tapping Remove logged `rc=0 remaining=28` yet "Aurelex Basic (DZ)" stayed in the refreshed list; a different dictionary had been unloaded
- [x] 1.4 Confirm the multi-select loop dispatched one independent `QtConcurrent` task per position, so out-of-order `g_engineMutex` acquisition could compound the mismatch

## 2. Carry the engine index in the exposed list

- [x] 2.1 In `refreshDictionaries`, insert `"engineIndex"` (the metadata read index `i`) into each dictionary map
- [x] 2.2 Leave the alphabetical sort and every existing field unchanged

## 3. Translate and batch the removal (app/DictionaryIndex.hpp, EngineController)

- [x] 3.1 Add header-only `DictionaryIndex` helpers (Qt Core only): `engineIndexForDisplay` and `removalTargets` (unique targets, highest engine index first)
- [x] 3.2 Change `removeDictionary(int)` to delegate to `removeDictionaries({index})` (signature unchanged)
- [x] 3.3 Add `removeDictionaries(QVariantList)` that resolves display positions to engine indices and captures each source path on the UI thread before any unload
- [x] 3.4 Unload the batch sequentially in one worker, highest engine index first, so an erase cannot shift a later target
- [x] 3.5 Keep the file/index deletion and FTS-queue cleanup on the UI thread after the worker, and refresh dictionaries/groups/count
- [x] 3.6 Log the resolved dictionary name and engine index, so a future mismatch is visible rather than silent

## 4. QML

- [x] 4.1 Change `_removeSelected` to call `engine.removeDictionaries(sel)` once with the whole selection, then clear it
- [x] 4.2 Confirm selection still keys off display positions and the By-Pair/All-order paths are unaffected

## 5. Tests

- [x] 5.1 Add `app/tests/DictionaryIndexTest.cpp`: display order differing from engine order maps correctly; targets are unique and engine-descending; invalid/duplicate positions dropped; empty inputs
- [x] 5.2 Add a `dictionary_index_test` target to `app/tests/CMakeLists.txt` (Qt Core only)
- [x] 5.3 Build and run the host test; all checks pass
- [x] 5.4 Correct the `removeDictionary`/`moveDictionary` header comment that claimed indices match `dictionaries()`

## 6. On-device verification

- [x] 6.1 With 36 loaded dictionaries (display order != load order), selected "Aurelex Phrasebook (DZ)" at display position 6; the log showed `engIdx=32`, `removeDictionary result: rc=0 name=Aurelex Phrasebook (DZ) remaining=35`, and the row disappeared from the list while the count dropped 36 -> 35
- [x] 6.2 Selected "Aurelex Lingvo EN-RU (DZ)" (position 4) and "Aurelex Phrasebook" (position 5) together; the batch logged `requested: 2`, resolved `engIdx=31` and `engIdx=29` (highest first), removed both named dictionaries, dropped the count 35 -> 33, and left the three unselected "Aurelex Lingvo EN-RU" entries untouched
- [x] 6.3 The log names the selected dictionary and its resolved engine index (`- <name> engIdx=NN src=...`), and the removal deleted each dictionary's `files/index/<id>` + `<id>_FTS_x` and its staged source file, keeping the shared staged folder
