## Context

`folder-scoped-storage` adds dictionaries via SAF and stage-copies them into
app-private storage; `gd_fts_index`/`gd_fts_index_state` (carve) already expose
per-dictionary index build and state. Currently indexing is manual per dict (an
"Index" button) and runs on a `QtConcurrent` worker. For large dictionaries a
build can be long, and when the app is backgrounded QtConcurrent work tied to the
process may be suspended. This change makes indexing automatic, bulk, and
background-resilient.

## Goals / Non-Goals

**Goals:**
- Build missing FTS indexes automatically, in bulk, after dictionaries are added.
- Run long builds on a background service so they survive app backgrounding.
- Keep the UI responsive with an in-progress indicator; no per-dict Index button.

**Non-Goals:**
- Re-architecting the carve engine (gd_* boundary already covers index build).
- Distributed/cloud indexing.
- Per-progress-bar-per-dictionary UI granularity beyond a single indicator.

## Decisions

### D1. Trigger auto-index after scan in EngineController
`runScan`'s completion handler already refreshes dictionaries/groups; it will also
call a new `autoIndexMissing()` that lists dicts with `gd_fts_index_state==1`
(missing/stale) and builds them. This covers both initial load and rescans.
- *Alternative:* index lazily at first search — rejected: the first search would
  block while building, and FTS would feel broken until a dictionary is touched.

### D2. Bulk build on a dedicated worker, not one `QtConcurrent` per dict
Build all missing indices sequentially inside a single `QtConcurrent::run`
(fine-grained per-dict tasks add queue churn and the engine serializes on
`g_engineMutex` anyway). `buildingFts` stays true across the whole batch; the
UI shows one indeterminate progress indicator.
- *Alternative:* one future per dict — rejected: no parallelism benefit (engine
  mutex serializes) and more bookkeeping.

### D3. Background service for long builds
For builds that may outlive the activity, run the batch on an Android
foreground service (`ExperimentActivity`/a small `IndexingService`) that owns the
worker. The service keeps a foreground notification while indexing; it calls the
carve `gd_fts_index` directly (the app is in-process), so no IPC is needed.
`EngineController` tracks the service's completion via a shared-preferences
marker (existing poller pattern) or a bound callback.
- *Alternative:* keep everything on QtConcurrent tied to the process — rejected:
  Android can suspend/background a process and long builds would stall.

### D4. UI
Drop the per-dictionary "Index" ToolButton from the Dicts pane. The FTS pane
keeps its single `buildingFts` indeterminate ProgressBar ("Indexing..." label)
covering the bulk build. `ftsIndexState` remains available for per-dict status if
a future UI wants it.

## Risks / Trade-offs

- [Long build at startup delays "indexed" status for the whole batch] → Indexed
  per-dict as each completes (`gd_fts_index_state` flips); a searchable dict is
  usable before the batch finishes.
- [Foreground service adds a notification the user sees] → Required by Android to
  keep background work alive; shown only while indexing.
- [Duplicate builds if scan re-runs mid-build] → `autoIndexMissing` skips when
  `buildingFts` is already set; index-state check avoids re-building existing.
- [Service vs. carve lifecycle] → In-process service calls gd_* under the engine
  mutex like the UI thread does; the existing `g_engineMutex` already guards this.

## Migration Plan

1. Land automatic `autoIndexMissing` after scan (D1/D2) behind the current
   `buildingFts` indicator.
2. Replace the per-dict Index button with the automatic flow; keep `ftsIndex`
   invokable for manual/testing use.
3. Add the foreground `IndexingService` for long builds (D3).
   Rollback: revert to manual Index button; automatic indexing is independent.

## Open Questions

- Whether to keep `ftsIndex`/the Index button for power users (currently leaning:
  drop from UI, keep the engine call). Resolved by user preference during apply.
- Notification-channel/foreground-service permission specifics on Android 13+.
