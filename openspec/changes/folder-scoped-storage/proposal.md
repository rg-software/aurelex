## Why

The current "Add dictionaries" flow requests system-wide All-Files-Access
(`MANAGE_EXTERNAL_STORAGE`) and then scans a fixed `/GoldenDict` folder on
external storage. Broad, unnecessary, and Play-policy-hostile. The project's
original design (goldendict-mobile-port) already resolved on **SAF folder-scoped
access** (OpenDocumentTree, no broad permission); the QtQuick experiment drifted
to AFA for expediency. Restore the folder-scoped model and let the user add
dictionaries from inside any allowed location(s) instead.

## What Changes

- "Add dictionaries" opens the Android SAF **folder picker**
  (`ACTION_OPEN_DOCUMENT_TREE`) instead of the All-Files-Access settings deep link.
- Picked folders become **persisted dictionary sources**: the SAF grant is kept
  (`takePersistableUriPermission`), so the location stays available across
  restarts. Multiple locations are supported.
- Each source is **resolved to a physical path** when the provider allows
  (e.g. `primary:` tree → `/storage/emulated/0/...`); that folder is scanned in
  place. When the provider cannot be resolved to a physical path (e.g. cloud
  storage), its dictionaries are **stage-copied into app-private `files/staged`**
  and scanned there.
- The sandbox `files/staged` folder remains an always-available source.
- **BREAKING** — Remove the broad `MANAGE_EXTERNAL_STORAGE` permission and the
  `isAllFilesAccessGranted` / `openAllFilesAccessSettings` / `externalStoragePath`
  flow. There is no system-wide storage access path anymore.

## Capabilities

### New Capabilities

- `storage-folder-access`: persisted, folder-scoped dictionary sources via the
  Android SAF — picking a folder, keeping its grant across restarts, listing the
  active sources, and resolving/removing them. (Covers the permission + grant
  lifecycle; scanning itself stays in `dictionary-management`.)

### Modified Capabilities

- `dictionary-management`: the "Dictionary folder selection and scanning"
  requirement changes — a folder is now selected from inside an allowed
  (folder-scoped, persisted) location rather than a system-wide grant + fixed
  `/GoldenDict` path, and scanning covers in-place (resolved path) and staged
  (stage-copy fallback) sources.

## Impact

- `experiments/qtquick/EngineController.cpp/.hpp` — replace the AFA storage
  helpers with: launching the SAF picker, persisting URI grants, resolving a tree
  URI to a physical path, and a multi-source `runScan` (in-place or staged).
- `experiments/qtquick/android/.../ExperimentActivity.java` — `OpenDocumentTree`
  launcher + `takePersistableUriPermission` + a path-resolution helper.
- `experiments/qtquick/android/AndroidManifest.xml` — remove
  `MANAGE_EXTERNAL_STORAGE`.
- `experiments/qtquick/main.qml` — the Add-dictionaries button flow (picker +
  source list instead of the AFA settings toggle).
- `carve` — unchanged (still scans a physical directory path, top-level only).
  The top-level-only scan constraint becomes a documented limitation for the
  in-place case.
