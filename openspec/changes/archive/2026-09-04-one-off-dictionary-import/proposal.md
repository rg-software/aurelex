## Why

The current model treats dictionary folders as persistent "sources": a folder
picker adds a source, a Rescan button re-pulls sources' folders, "Remove" only
unloads the in-memory dictionary (leaving it on disk and still present in the
source), and sources persist across restarts with their SAF grants. On Android
with scoped storage this buys little — we stage-copy every source into
app-private storage anyway, so "rescan" is just "re-copy," and the extra
management surface (sources list, Rescan, `refreshSources()`, grant
persistence, source-dedup) has been the source of most bugs in this exercise.

Move to a one-off import model, matching phone UX and golden-dict-mobile's
approach: pick a folder -> the dictionaries are imported (stage-copied,
scanned, indexed) immediately; there is no sources list and no Rescan; Remove
permanently deletes the imported copy (files + indexes) from the app.

## What Changes

- **BREAKING** — remove the persistent "sources" model:
  - No admin-pick dictionary sources list in the Dicts tab; "Add dictionaries"
    imports immediately (stage -> scan -> auto-index).
  - Remove the Rescan button and `EngineController::rescan()` /
    `refreshSources()` / the `refresh.xml` completion-marker flow.
  - Picked SAF grants are consumed only long enough to stage-copy; the grant
    does not need to persist (the staged copy is authoritative). Existing
    persisted grants for previously-added sources are dropped on first launch
    after upgrade (existing staged copies remain and re-scan normally).
- `removeDictionary` (and the "Remove" confirm flow) now **permanently** deletes
  the imported dictionary:
  - removes the dictionary from the engine (existing `gd_remove_dict`),
  - deletes the corresponding staged copy under `files/staged/<id>` when it is
    the last/only dictionary of that staged dir,
  - deletes the dictionary's index cache (`index<id>*` / `index<id>_FTS_x`),
  - releases the folder grant if still held.
- Dictionaries live on only in app-private storage; no periodic re-sync means a
  folder holding the original files can be deleted/moved without affecting the
  app's copies.
- Dicts tab shows dictionaries; per-dictionary Remove with confirmation.

## Capabilities

### New Capabilities

(none — this reframes existing behavior rather than introducing a new surface)

### Modified Capabilities

- `storage-folder-access`: source list persistence, Rescan/source management,
  and in-place/resolvable scanning are removed. Folder selection (SAF picker)
  remains; the grant is used only to stage-copy once (import), not persisted
  management. Requires the "persisted grants"/"multiple sources"/"resolve and
  scan in place" requirements to be replaced by a one-off-import contract.
- `dictionary-management`: added-sources model replaced with one-off import;
  "Remove a loaded dictionary" becomes permanent deletion of the imported copy
  (files + index); removed/re-add behavior and the "sources" wording change.
- `full-text-search`: an imported dictionary's index life cycle is tied to the
  imported copy — deleting the dictionary deletes its index.

## Impact

- `EngineController.{hpp,cpp}` — delete `m_sources`, `addDictionaryFolder`
  rework, `removeSource`, `rescan`, `peekPendingSourceUri`,
  `ingestPendingSource`, `removePendingSourceFile`, `peekPendingRefreshFlag`,
  `refreshSources` paths; `removeDictionary` gains delete-on-disk logic.
- `main.qml` — Dicts tab: remove Sources section + Rescan; keep Add + Remove;
  confirm dialog now states permanent deletion.
- `app/android/.../AurelexActivity.java`, `StagingService.java` — keep
  stage-copy into `files/staged/<id>`; do not write/send `source.xml` for
  grant persistence; remove the refresh/preferences paths.
- `app/settings.json` — `sources` array removed from persistence.
- Docs (`docs/*`, `AGENTS.md`) reflect the new storage model.
- No `engine/` or carve source edits.