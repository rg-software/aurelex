# Tasks

- [x] **EngineController: queue-based FTS worker** (design D1/D2)
  - Replace per-scan `autoIndexMissing` batches with `QList<int> m_ftsQueue`
    draining worker.
  - Rework `autoIndexMissing` to ENQUEUE missing indices (append
    not-already-queued; start the single worker if idle).
  - Worker: pop idx → `gd_fts_index_state` re-check (skip if built) →
    `gd_fts_index` → increment done → emit `ftsIndexBatchProgress`.
  - Clear `buildingFts` only when queue empty.
- [x] **EngineController — remove generation guard**
  - Delete `m_ftsBatchGeneration` and the "stale batch" check (no longer
    needed single-worker).
- [x] **Progress properties now derive from the queue**
  - `ftsIndexTotal` = current queue size; `ftsIndexDone` monotonic; per-run
    invariants per design D3. Reset on queue-empty.
- [x] **Java — queue pending folder picks** (design D4)
  - `AurelexActivity.onActivityResult`: when `sStagingRunning`, push tree/
    display onto a static `ArrayDeque` instead of dropping.
  - `StagingService`: after finishing each copy, pop next pick; loop until
    queue empty. On failure log + continue.
- [x] **Manual device verification**
  - Two-dict import indexed live; no UI freeze (UI-thread watcher fired while
    worker churned), single FTS worker drained the queue, `buildingFts` cleared
    only when the queue emptied (verified via adb: `FTS worker finished a
    drain` on the UI thread during indexing + `IndexingService stopped`).