## Context

The QtQuick app currently gets dictionaries via All-Files-Access: the manifest
declares `MANAGE_EXTERNAL_STORAGE`, `isAllFilesAccessGranted()` / `openAllFilesAccessSettings()`
/ `externalStoragePath()` gate the flow, and `runScan` switches to scanning
`/storage/emulated/0/GoldenDict` when the broad grant is active (see proposal.md —
Why). The carve reads dictionaries through **physical paths** (`QDir`/`QFile`),
never content URIs, and `gd_scan_dicts` scans a single directory **top-level only**
(no recursion). The app is in-process (no separate `:engine`), so a URI grant held
by the app process is available to the carve — but the carve still needs a physical
path. The established Java-shell pattern here is JNI from `EngineController` via
`QJniObject` into static `ExperimentActivity` methods (e.g. `isNightModeActive`),
with Java writing a file (`shared_prefs/intent.xml`) that a C++ `QTimer` poller
(`m_pollTimer`) consumes. The archived Kotlin port already implemented the SAF
equivalent (`SafResolver.resolveTreePath` + `stageDictionaryFiles`); this change
brings that model to QtQuick.

## Goals / Non-Goals

**Goals:**
- Folder-scoped dictionary sources via `ACTION_OPEN_DOCUMENT_TREE`, with persisted
  grants and multiple sources.
- In-place scan when a source resolves to a physical path; stage-copy fallback
  otherwise.
- Remove the All-Files-Access path entirely.

**Non-Goals:**
- Recursive dictionary scanning (carve stays top-level-only; nested folders in a
  picked location are a documented limitation). **Tracked as a separate follow-up
  task** (see tasks.md section 6) — not part of this change's acceptance.
- Cloud-provider browsing UX (unresolvable providers are stage-copied).
- Copying large `.mdd` for resolvable folders (in-place scan avoids duplication).

## Decisions

### D1. SAF folder picker lives in the Java shell (`ExperimentActivity`)
C++ calls `ExperimentActivity.pickDictionaryFolder()` via `QJniObject` (same shape
as today's `openAllFilesAccessSettings`). The picker is launched with
`ACTION_OPEN_DOCUMENT_TREE` + `FLAG_GRANT_READ|WRITE|PERSISTABLE_URI_PERMISSION`.
The result arrives in `ExperimentActivity.onActivityResult` (Qt's `QtActivity`
forwards activity results to the subclass); Java calls `takePersistableUriPermission`,
resolves the path, and writes the new source into a file the existing C++ poller
reads (mirroring the `intent.xml` pattern).
- *Alternative:* `ActivityResultLauncher` (modern AndroidX) — rejected: it owns its
  own lifecycle callbacks that clash with Qt's activity delegate in 6.6.
- *Alternative:* a Qt Quick `OpenDocumentTree` QML type — doesn't exist in 6.6.

### D2. Path resolution in Java (`resolveTreePath`) — display only
`DocumentsContract.getTreeDocumentId(uri)` returns e.g. `primary:Download`.
- `primary:<rel>` → `/storage/emulated/0/<rel>`, `<volume>:<rel>` → `/storage/<volume>/<rel>`,
  anything else → empty.
- **This is a display label only.** Under scoped storage the app cannot read
  `/storage/emulated/0/<rel>` via `QDir`/`QFile` without All-Files-Access, so the
  engine can never scan the resolved path. The label keeps the Sources list
  human-readable (e.g. "GoldenDict") while the actual scan uses the staged copy.

### D3. Always stage-copy in Java (`stageTree`) — incremental
For every added source, Java enumerates the `DocumentFile` tree (matching how the
carve will scan) for files ending in `.mdx`/`.mdd`/`.dsl`/`.dsl.dz`/`.ifo` and
copies them into `files/staged/<sourceId>/`. C++ scans that staged subdir. Copying
must be Java-side because only Java can read the SAF content URIs, and it is always
required: a physical path is unreadable by the engine under scoped storage.
The copy is **incremental**: for each file, skip if the destination already exists
with the same size and close last-modified time (the destination is stamped with
the source's mtime), so a re-pull only copies changed files — large unchanged
`.mdd` files are not re-copied.
- *Alternative:* scanning the resolved path in place — rejected: scoped storage
  blocks direct path reads; the archived Kotlin port reached the same conclusion.

### D4. Multiple sources, persisted in C++ settings.json
`settings.json` gains a `sources` array: `[{ "uri", "path"?, "orig", "staged" }]`.
`runScan` loops the sources, calling `gd_scan_dicts` once per resolvable physical
dir (a resolved path, or the staged subdir), accumulating `dictCount`; sources whose
folder is gone/revoked are logged as unavailable and skipped, so one bad source does
not fail the scan of the others. The sandbox `files/staged` root stays as one
always-available source (its default scan unchanged).

### D4a. "Rescan" re-pulls the ORIGINAL folders, not the staging
The private staging reflects a snapshot and can only change through our own writes,
so re-scanning it would be a no-op — or worse, stale. The **Rescan** action therefore
means "re-read my dictionary folders": `EngineController.rescan()` asks the Java
shell to run `refreshSources()`, which reads `settings.json`, re-runs the incremental
`stageTree` for every persisted SAF source (copying only changed files), then writes
`shared_prefs/refresh.xml`; the C++ poller sees it and runs `runScan()` over the
refreshed staging. Removing a source **deletes its staged copy** (`QDir::removeRecursively`
on `files/staged/<sourceId>`) after unloading its dictionaries — it is only our
snapshot; the original user folder is never touched.

### D5. Remove All-Files-Access
Delete `MANAGE_EXTERNAL_STORAGE` from the manifest, drop
`isAllFilesAccessGranted`/`openAllFilesAccessSettings`/`externalStoragePath` from
`EngineController`, and remove the AFA branch in `runScan`. `runScan` becomes
source-driven rather than AFA-gated.

### D6. UI: picker + sources list
"Add dictionaries" always opens the SAF picker (no storage-grant branch — the
`storageGranted` timer check is removed). The Dicts pane lists active sources (name +
path/staged indicator) with a remove action; removing a source triggers the
"Remove a source" spec scenario (dicts vanish from list/lookup/FTS).

## Risks / Trade-offs

- [Qt's `onActivityResult` may not be invoked in some Qt 6.6 Android lifecycles]
  → Verify on-device first (task), and if the subclass override is not delivered,
  fall back to launching the picker with a callback id through
  `QtActivityDelegate` / the Qt native `startActivityForResult` API.
- [Secondary-volume `/storage/<id>/<path>` guess is wrong on some devices]
  → Treat as unresolvable (empty path) → stage-copy, which is always safe.
- [Top-level-only carve scan misses dictionaries in nested folders of a picked
  location] → Documented limitation; the picker's "use this folder" + plain
  guidance mirrors the old port; recursion is a future carve change.
- [Staging large `.mdd` doubles disk usage] → Staging is required for every
  source (scoped storage blocks in-place reads); index cache stays in app-private
  storage. Accepted for v1, matching the archived Kotlin design.
- [Persisted grant revoked (user or unmount)] → Source marked unavailable and
  skipped; user re-adds via the picker.
- [Existing `/GoldenDict` data no longer readable after AFA removal]
  → Sources start empty; user re-adds the folder through the picker (it is
  resolvable as `primary:GoldenDict` → `/storage/emulated/0/GoldenDict`, scanned
  in place with no copy). No migration copies needed.

## Migration Plan

1. Add SAF source support behind the current flow, keeping AFA until the picker
   path is on-device-verified.
2. Flip: "Add dictionaries" opens the picker; seed sources from
   `/storage/emulated/0/GoldenDict` if present (one-time, in-place).
3. Remove AFA (`MANAGE_EXTERNAL_STORAGE` + helpers) once picker flow is stable.
   Rollback: restore the AFA branch + manifest permission from git.

## Open Questions

- Whether `QtActivity` delivers `onActivityResult` to the `ExperimentActivity`
  override on the target device (resolved by the verify task in D1's risk).
- Whether secondary-volume path resolution should use `StorageManager` instead of
  the `/storage/<id>` guess (currently safe to defer — fallback is stage-copy).
