## Why

A dictionary staged at a source path of 512 bytes or more is loaded by the engine but
omitted from the Dictionaries list: the app reads each dictionary's source path through a
fixed 512-byte buffer, and `gd_dict_info` refuses the entry rather than truncating it, so
the row is skipped. The dictionary still answers lookups, but it cannot be seen or removed —
removal is only reachable from the list, and the staged sweep deliberately retains any
directory that holds a primary dictionary file (`fix-stale-sweep-deletes-live-dictionaries`),
so nothing else reclaims it. Short of clearing the app's data — which destroys every other
staged dictionary and its indexes — the user has no way to get the space back.

Reproduced on device while verifying that earlier change: a valid dictionary at a 530-byte
staged path was counted by `gd_dict_count` but appeared in **neither** the Dictionaries list
nor the sweep's in-use set, while an otherwise identical copy at 500 bytes was listed
normally. So the boundary sits exactly where the code reads.

This is borderline in likelihood and irreversible when it happens. The app fixes 64 bytes of
the path (package name plus `files/staged/<sourceId>/`), leaving roughly 447 bytes for the
user's own folder tree; because the comparison counts UTF-8 **bytes** and not characters, a
deep non-Latin collection reaches the limit at roughly a third of the apparent depth. Nothing
is corrupted and no data is lost — it is a management dead end, not the silent deletion the
preceding change fixed.

## What Changes

- Raise the app-side dictionary-info buffers from 512/256 bytes to `PATH_MAX` (4096), so any
  path or name a legal filesystem can produce is returned instead of refused. The buffer size
  is the **caller's** choice — `gd_dict_info` takes `file_size` as a parameter and copies
  whatever fits — so this needs no boundary, engine, or `patches/` change.
- Apply that size at both call sites that request a source path, not just the one the
  Dictionaries list reads, so the FTS indexing loop cannot label a dictionary differently
  from the list that shows it.
- Add the completeness requirement this defect violates: every dictionary the engine has
  loaded is listed, and therefore removable, whatever the length of its staged path.
- Leave the staged sweep's behaviour unchanged. A directory holding a primary dictionary file
  is still retained, so this change cannot reintroduce the deletion the preceding change
  fixed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: adds a requirement that the loaded-dictionary set the app exposes
  is complete — every dictionary the engine loaded is listed and removable — regardless of
  the length of its staged source path.

## Impact

- `app/EngineController.cpp` — `readDictInfoAt()`, the single place the boundary's
  dictionary-info call is made for a source path, and the FTS indexing loop's separate
  dictionary-info call. Both use fixed buffers today (512 bytes for the path, 256 for the
  name).
- No `carve/` change, no `patches/` entry, no engine-submodule change: the limit is the app's
  own buffer, not an API constraint.
- No persisted state and no layout change, so rollback is a plain revert.
- Severity for scheduling: no data loss, no user-visible regression for any user whose paths
  fit the current buffer, and low incidence. It repairs a dead end rather than a breakage,
  which is why implementation may be deferred without holding up the release that carries the
  deletion fix.
