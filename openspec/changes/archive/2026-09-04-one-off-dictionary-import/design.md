## Context

The app's storage model is source-based: "Add dictionaries" → adds a *source*
(folder + persisted SAF grant); Rescan re-pulls sources into staging; "Remove"
on a dictionary only unloads it in memory (its file stays, and it reappears on
next Rescan). `EngineController` carries `m_sources`, the `sourcesChanged`
property, `addDictionaryFolder`/`removeSource`, `rescan`,
`ingestPendingSource` + the `source.xml`/`refresh.xml` SharedPreferences
markers, and `loadSettings/saveSettings` persist the `sources` array. This
whole "sources" management surface is the source of most complexity, and its
Rescan story is a red herring on scoped storage (every source is stage-copied
anyway).

See proposal.md for motivation; spec deltas define the new behavior contract.

## Goals / Non-Goals

**Goals:**
- Pick folder → one-off import (stage-copy → scan → auto-index).
- Remove a dictionary permanently deletes its staged files + indexes.
- Delete Rescan, the sources list/UI, `refreshSources`, `source.xml`/
  `refresh.xml` markers, and persisted-source grant logic.

**Non-Goals:**
- No changes to the carve/engine or the C `gd_*` API.
- No change to groups / active group / history / favorites.
- No dedup-migration of existing staged files is needed (they just re-scan).

## Decisions

### D1. Dictionary set = the staged files; drop `m_sources`
`m_sources`, `sources()`/`sourcesChanged`, `removeSource`, `rescan`,
`addDictionaryFolder`'s "source" semantics, `ingestPendingSource`,
`peekPendingSourceUri`, `removePendingSourceFile`, `peekPendingRefreshFlag`,
`removePendingRefreshFile`, and the Android
`pickDictionaryFolder`→`source.xml`/`refreshSources`→`refresh.xml`
pipeline are removed. The dict list (`gd_dict_count`/`dict_info`) is the
single source of truth, backed by app-private `files/staged/`.

- **Import flow**: `addDictionaryFolder()` still launches the SAF picker in
  Java (`AurelexActivity`); the service stage-copies into
  `files/staged/<sourceId>`; on completion it writes a marker the poller
  consumes to call `runScan()` — but the `source` is NOT recorded anywhere.
  The staged dir *is* the import; scanning it is enough. (If it no longer
  needs identifying, we can even flatten to the existing `staged` root —
  keep per-dir for now to preserve file dedup across re-imports.)
- Java: stop persisting/taking *persistable* SAF grants. The picker still
  returns a URI; the activity uses it to `openInputStream` (transient) during
  the copy and releases it. `releaseSourcePermission` (SAF release) no longer
  needed at remove-time.
- `settings.json` no longer stores `sources`; existing `settings.json` with a
  `sources` array is read but the array ignored (backward compatible: staged
  files remain and re-scan).

### D2. Remove = permanent delete
`removeDictionary(index)` gains on-disk cleanup before/after
`gd_remove_dict(index)`:
1. `gd_dict_info(index,...)` → the primary source file path (e.g.
   `files/staged/<id>/sub/dict.mdx`).
2. Walk up to the `files/staged/<id>` dir; `QDir(removedPath).removeRecursively()`
   only if no other loaded dictionary's source starts with that dir (avoid
   deleting a sibling dict in the same staged import).
3. Delete the engine index cache for that dict id
   (`files/index<md5>[*]`, `files/index<id>_FTS_x`, `_temp`).
4. `gd_remove_dict` as today; refresh lists (dicts/groups/FTS).

To delete the index cache we need the engine's dictionary id (md5 hex) as the
index-file prefix. That is not exposed by the `gd_*` boundary, so the carve
gains a small read-only accessor `gd_dict_id(int index, char* out, int out_size)`
(same pattern as `gd_dict_info`) in `gd_boundary.cc`. This is the only carve
addition and it does NOT touch upstream engine sources.

### D3. UI
- Dicts tab: remove "Sources" label + sources `ListView` + Rescan button.
  Keep "Add dictionaries" primary button. Dictionary rows keep "Remove",
  whose confirm dialog now says the app copy of the dictionary (files + index)
  will be deleted permanently.
- `root._openDicts()` and `_openGroups()`/FTS use unchanged.
- The `engine.sources` property goes away; check main.qml for
  `engine.sources`/`scanFailures` references and drop/update.

## Risks / Trade-offs

- [Re-import dedup across staged `<id>` dirs] → keep the existing `stageTree`
  dedup (name/size/mtime hash) as-is; the import just doesn't register a
  "source".
- [Remove while a staged dir is shared by several dicts] → walk-up + check
  remaining dicts before deleting the dir; if shared, leave the dir
  (unexported files for the other dicts remain) and remove only the single
  dict + its index.
- [Existing installs: staged copies from old "sources" survive] → they re-scan
  on first launch after upgrade; the Sources list is gone, but every dict the
  user added via Add still chunks; no data loss.
- [SAF grant dropped but user edits the original folder] → imports are
  snapshots; the app won't see future edits without a fresh re-import (by
  design).

## Migration Plan

1. Drop `m_sources` + source plumbing; the picker writes no `source.xml`;
   poller only looks for staging-done marker.
2. Remove Rescan/Sources UI in QML + QCM controller paths.
3. Make Remove delete staged files + index.
4. Verify: import folder → appears; kill app → reopens with dict loaded (from
   staged); Remove → dict + files + index gone; relaunch → still gone.
5. Rollback: `git` revert; `settings.json` source arrays are simply ignored,
   so nothing gets broken by an upgrade/downgrade.

## Open Questions

- Whether to keep the per-import subdir (`staged/<sourceId>`) or flatten to
  one root: keeping per-dir is safest for the walk-up delete; flattening would
  need file-level provenance tracking. Keep per-dir now.