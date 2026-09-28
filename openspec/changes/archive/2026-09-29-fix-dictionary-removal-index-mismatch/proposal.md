## Why

Removing a dictionary removes the wrong one. `EngineController::refreshDictionaries`
sorts the exposed dictionary list alphabetically by name, but `removeDictionary`
passed the caller's position in that sorted list straight to `gd_dict_id` /
`gd_remove_dict`, which take the engine's own (scan/insertion) index. Whenever
the two orders differ - which they do as soon as more than a handful of
dictionaries are loaded, or any two names sort differently from load order - the
removal targets a different dictionary than the one selected. The selected row
stays in the list, so the tap appears to do nothing.

Device evidence (2026-09-28, Motorola ThinkPhone, 29 loaded dictionaries):
selecting "Aurelex Basic (DZ)" and tapping Remove logged
`removeDictionary requested: Aurelex Basic (DZ) ... idx=3` followed by
`removeDictionary result: rc=0 ... remaining=28`, yet "Aurelex Basic (DZ)" was
still in the refreshed list; a different dictionary had been unloaded and its
index deleted. The intended dictionary's staged file *was* deleted (the app used
the display entry for that), so a restart then re-added the dictionary that was
silently removed while the selected one was gone on disk - the classic "deleted
dictionaries reappear / the wrong one disappears" report.

A second defect compounds it: multi-select removal dispatched one independent
`QtConcurrent` task per selected index. Even with correct engine indices those
tasks can acquire `g_engineMutex` out of order, so after one erase shifts the
list, a later task can remove the wrong dictionary.

## What Changes

- **Carry the engine index with each exposed dictionary.** Each entry in
  `EngineController::dictionaries()` gains an `engineIndex` field, so the app
  always knows which engine slot a displayed row refers to.
- **Translate display position to engine index on removal.** `removeDictionary`
  and a new `removeDictionaries` resolve the caller's positions to engine
  indices before calling the boundary; the mapping is a header-only helper
  (`app/DictionaryIndex.hpp`) so it is testable without the engine.
- **Remove a multi-selection as one ordered batch.** The selected dictionaries
  are unloaded by a single worker, highest engine index first, so an erase can
  never shift a target that has not been removed yet.
- **Show the resolved dictionary in the log.** The removal log names the
  dictionary and its engine index, so a mismatch is visible rather than silent.

No engine change: `engine/` stays byte-for-byte at the pinned tag, no
`patches/` entry, no upstream delta. The boundary's "index" contract is
unchanged; the app simply stops violating it.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities

- `dictionary-management`: "Remove a loaded dictionary" is strengthened so the
  dictionary that is removed is unambiguously the one the user selected,
  independent of the list's display order, and so a multi-select removal
  removes exactly the selection (each still identified by the dictionary, not
  by a position that may shift).

## Impact

- Affected code:
  - `app/EngineController.cpp` - `refreshDictionaries` records `engineIndex`;
    `removeDictionary`/`removeDictionaries` resolve it and batch the removal.
  - `app/EngineController.hpp` - declares `removeDictionaries`; corrects the
    "indices match dictionaries()" comment.
  - `app/DictionaryIndex.hpp` - new header-only display/engine mapping helper.
  - `app/main.qml` - `_removeSelected` calls `removeDictionaries` with the
    whole selection in one call.
  - `app/tests/DictionaryIndexTest.cpp` + `app/tests/CMakeLists.txt` - new host
    test and target.
- Affected APIs: none. No `gd_*` boundary function changes.
- Affected dependencies: none. No new engine source, no patch, no upstream bump.
- Upstream fidelity: `engine/` unchanged.
- Localization: no user-visible English text changes; `scripts/update-translations.ps1`
  is not needed.
