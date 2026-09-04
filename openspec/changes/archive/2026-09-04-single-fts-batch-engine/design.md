## Context

Today `EngineController::autoIndexMissing()` spins up an independent
`QtConcurrent`+`QFutureWatcher` batch per scan: it computes the "missing"
set, sets `buildingFts`, runs `gd_fts_index(idx)` serially, and clears the flag
in that batch's own `finished` handler, protected by a `m_ftsBatchGeneration`
counter added to stop a stale batch clearing a newer one. Adding a folder
mid-build starts a *second* batch; both workers serialize on the engine mutex
but can re-index the same dictionary (double work), and progress jumps.

Separately, `AurelexActivity.onActivityResult` only stages a pick if
`sStagingRunning` is false, silently dropping a second any pick.

## Goals / Non-Goals

**Goals:**
- One FTS worker at a time, driven by a queue; dictionaries added mid-build are
  enqueued, never double-built, and the "N of M" total grows.
- Folder picks made during a running stage-copy are queued and processed in
  order, not dropped.

**Non-Goals:**
- No change to the engine/carve (`gd_fts_index`/`gd_fts_progress` unchanged).
- No parallel indexing; sequential queue only.
- No UI relayout.

## Decisions

### D1. A single worker loop drains a `QList<int>` queue
`EngineController` owns `QList<int> m_ftsQueue` (dictionary indices pending
index). `autoIndexMissing()` (renamed `enqueueMissingForFts()`) computes the
current missing set, appends each not-already-queued index, recomputes
`ftsIndexTotal = queue.size()` + running done count, and kicks the worker if
not running. The worker `QtConcurrent::run` loop pops index, guards
"skip if already indexed (haveFTSIndex via `gd_fts_index_state`)" to avoid
double work, runs `gd_fts_index`, increments done, and emits
`ftsIndexBatchProgress(done, total, name)`. When the queue is empty it
finishes and clears `buildingFts` — and *only then*. Any new scan that appends
mid-run simply re-appends and the worker keeps going (no generation guard
needed).
- *Alternative*: keep per-scan batches + generation counter (current). Rejected:
  still double-builds; totals don't grow; generation logic is fragile.

### D2. The worker re-checks `haveFTSIndex` before indexing
Because a dictionary may have been indexed by an earlier worker round-trip (or
a previous batch), the queue entry itself is not a guarantee of "needs build".
Each dequeued index first queries `gd_fts_index_state`; if already built,
skip (count it done). This is the single enforcement point for "never index
twice".

### D3. Progress properties derive from the queue invariants
- `ftsIndexTotal` = number of items currently in the queue (grows as dicts are
  added).
- `ftsIndexDone` = count of completed items (monotonic within a run).
- `ftsDictFraction` = `gd_fts_progress` percent of the current item
  (unchanged).
- `ftsIndexFraction` = `done / total` (unchanged, but total can now grow).
The UI's two bars (per-dict + all-dict) keep the same semantics the user
approved; only the driver changes.

### D4. Pending stage picks as a Java queue
In `AurelexActivity::onActivityResult`, if `sStagingRunning` is true, push the
incoming `treeUri` + display into an in-memory `ArrayDeque` instead of
dropping. `StagingService` pop next from the queue after finishing the current
copy (loop while items remain), single-flight still enforced. On failure
surface (log / lastError) and continue to the next queued pick.

## Risks / Trade-offs

- [Worker emit of `ftsIndexBatchProgress` from a background thread] → queued
  connect to `EngineController` (main-thread affinity) already in place.
- [Adding a dict whose index is already building (index-in-progress state
  `1`)] → D2 re-check makes the app re-append; skip only covers already-built;
  an in-progress item may be re-queued and then skipped by D2's recheck.
  Mitigate further by tracking `gd_fts_index_state` at enqueue time.
- [Queue indefinite growth if a pathological dict keeps failing] → treat each
  dequeued item as "attempted"; a failed index (rc != 0) is counted done and
  removed; batch completes. A resurge prompt can re-import it if needed.

## Migration Plan

Pure internal change; no persisted state. Install & verify: (1) add a large
folder; (2) while building, add another; expect the total to grow and the dicts
to be indexed once; progress bar stays live. (Verify the "never twice" log
line count == number of dicts.)

## Open Questions

None material.