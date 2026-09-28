## Why

Re-importing an updated dictionary wedges the Search field and can kill the app.

Reproduced on device 2026-09-28: search `swop` in the Kaikki group works, then
import a new build of the same dictionary (same folder, same file name), let the
import and indexing finish, and typing `sw` yields no dropdown. The log shows
`gd_suggest word=swop mutex=0ms pump=9870ms finished=0` - the engine burned its
full 10 s bound and returned nothing, and `Index searching failed: "kaikki-en",
error: Error reading from the file`.

Root cause is the ordering in `gd_scan_dicts` (`carve/gd_boundary.cc`): it calls
the backend factory for **every** primary file on **every** scan and only checks
the dictionary id **afterwards**:

```cpp
made = factory();                    // Dsl::makeDictionaries: rebuilds the index
for ( d : made )
    if ( loadedIds.contains( d->getId() ) )
        continue;                    // discard the freshly built object
```

A dictionary's id is an MD5 of its source **paths**, so a re-import into the same
folder with the same file name keeps the id. `Dsl::makeDictionaries` sees the new
file (mtime newer than the index) and **rewrites `<indexDir><id>`** - then the
scan discards the object it just built and keeps the old one, which still holds a
reader over the index file that was rewritten underneath it. Its prefix search
fails with "Error reading from the file", `WordFinder` never emits `finished`, and
`gd_suggest` blocks the engine for its whole timeout. A restart builds a fresh
object against the new index and works, which is why the failure is
session-scoped.

Two user-visible defects come out of this:

- The Search field stops returning suggestions after an import (and the
  `prefixMatch` never-finishes condition is what can push the app into an ANR /
  foreground-service timeout, i.e. the app dying).
- The update never takes effect in the running session: the new content is staged
  and indexed but the app keeps serving the old in-memory dictionary until a
  restart.

## What Changes

- **Reload a dictionary whose source files changed.** `gd_scan_dicts` records the
  size + mtime of each loaded dictionary's source files when it is loaded, and on
  the next scan drops any entry whose files no longer match. The scan then rebuilds
  it from the new file, so the new object reads the new index and the updated
  content takes effect. A dictionary whose files are unchanged is untouched, so a
  plain re-scan still does nothing and unchanged dictionaries keep their
  full-text-index state (no re-validation storm on every import).
- **Do not rewrite an index under a live dictionary.** With the stale entry
  dropped first, the backend's rebuild belongs to the object that will actually be
  kept, so there is no window where a live object reads a rewritten index.

No engine change: `engine/` stays byte-for-byte at the pinned tag, no
`patches/` entry, no upstream delta. The id scheme and index naming are upstream's
contract; the fix is in the boundary's scan policy.

## Capabilities

### Modified Capabilities

- `dictionary-management`: the import/scan capability gains the requirement that
  re-importing a changed dictionary reloads it in the running session - the new
  content takes effect without a restart, the reloaded dictionary searches
  normally, and a scan never leaves a dictionary reading an index that was
  rewritten for a newer version of itself.

## Impact

- Affected code:
  - `carve/gd_boundary.cc` - `EngineState` gains per-dictionary source stamps;
    `gd_scan_dicts` drops changed entries before the dedup and records stamps for
    what it keeps.
  - `carve/smoke/main.cpp` - `REIMPORT_RELOAD` / `REIMPORT_CONTENT` /
    `REIMPORT_SUGGEST` assertions in a new re-import block, folded into the exit
    code.
  - `.github/workflows/engine-smoke.yml` - the matching `grep` gates.
- Affected APIs: none. No `gd_*` function is added, removed, or changed.
- Affected dependencies: none. No new engine source, no patch, no upstream bump.
- Upstream fidelity: `engine/` unchanged.
- Localization: no catalogs touched; no user-visible English text changes.
- Session behavior: re-importing a changed dictionary rebuilds its index and
  re-runs its full-text index in the same session (it is a new object, so
  `haveFTSIndex` is false and the normal auto-index path covers it). Unchanged
  dictionaries are not affected.
