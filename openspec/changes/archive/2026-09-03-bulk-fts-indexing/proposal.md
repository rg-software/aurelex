## Why

Adding a dictionary currently leaves its full-text (Xapian) index unbuilt until
the user manually indexes it, and a large dictionary can take a long time to
index. The `folder-scoped-storage` change adds dictionaries via a folder picker,
but indexing is still triggered per-dictionary and can block the interaction. We
want dictionaries to be indexed automatically, in bulk, on a background service
so search + FTS "just work" without a manual button and without blocking the UI
for long-running builds.

## What Changes

- **Automatic bulk indexing**: when dictionaries are added (or a scan finds new
  ones), the app builds a full-text index for every loaded dictionary that lacks
  one, in bulk, without a per-dictionary manual "Index" action.
- **Background execution**: indexing runs off the UI thread; for long-running
  builds (large dictionaries) the work runs on a background service so it
  survives the app being backgrounded and keeps the UI responsive.
- **Progressive availability**: dictionaries become searchable as their index
  completes; the UI shows an in-progress state and does not block the rest of the
  app while indexing runs.
- Removes reliance on the manual per-dictionary Index button.

## Capabilities

### New Capabilities

- (none new)

### Modified Capabilities

- `full-text-search`: the "Full-text index" and "Index build progress"
  requirements change to specify automatic bulk indexing after dictionaries are
  added, background-service execution for long builds, and no manual per-dict
  Index action required for searchability.

## Impact

- `experiments/qtquick/EngineController.cpp/.hpp` — trigger automatic bulk
  indexing after scan; move long-running index builds onto a background worker.
- `experiments/qtquick/main.qml` — drop the per-dictionary Index button; surface
  an overall indexing-progress indicator.
- `experiments/qtquick/android/...` (Java) — a background service for long
  indexing runs (e.g. a foreground service) if the build outlives the activity.
- `carve` — unchanged (`gd_fts_index` / `gd_fts_index_state` already exist).
