## Why

Adding a dictionary folder while a full-text index batch is already running
currently starts a *second*, independent `autoIndexMissing` batch. The two
workers serialize on the engine mutex but can both try to index the *same*
dictionary (double work), the "N of M" totals restart from what's still
missing rather than growing, and the UI can briefly show two sources of truth.
Separately, a second folder pick while staging is in flight is silently dropped
(`sStagingRunning` single-flight), losing the user's selection.

## What Changes

- Replace the "one batch per scan" FTS indexer with a **single shared batch
  engine** in `EngineController`:
  - One worker loop consumes a queue of dictionary indices; dictionaries added
    mid-build are **appended** to the queue, not started in a rival batch and
    never double-built.
  - Batch totals grow live: `ftsIndexDone`/`ftsIndexTotal` reflect the whole
    queue, and the "All dictionaries" bar approaches 100% only when every
    queued dictionary is done.
  - The old batch's completion handler no longer clears `buildingFts` when a
    newer batch is active (already guarded, now structurally impossible).
- Queue **pending folder picks**: if a stage-copy is running when a pick
  returns, remember the tree URI and stage it as soon as the current copy
  finishes, instead of dropping it.
- Progress semantics stay: `ftsDictFraction` (this dictionary, resume-aware)
  and `ftsIndexFraction` (all dictionaries) unchanged in meaning, but sourced
  from the single worker's queue.

## Capabilities

### New Capabilities

- `full-text-search` (existing capability, modified below): the batch engine is
  an implementation/robustness change; no new capability needed.

### Modified Capabilities

- `full-text-search`: automatic bulk indexing must tolerate dictionaries being
  added *while* a bulk build is running — the batch must incorporate them
  without restarting, without double-indexing, and without losing progress
  indication. Adds a requirement/scenario for "add during indexing".
- `dictionary-management`: multiple folder additions in quick succession must
  all eventually take effect (no silently dropped pick while staging),
  reflected in the add-dictionaries behavior.

## Impact

- `EngineController.{hpp,cpp}` — new single-worker queue replacing
  `autoIndexMissing`'s per-scan `QtConcurrent`+`QFutureWatcher` batches;
  `ftsIndexDone/Total/Fraction/DictFraction/currentName` feeding from the queue.
- `AurelexActivity.java` / `StagingService.java` — pending-pick queue for
  folder additions (stage a serially, not concurrently).
- No carve/boundary change; no spec-breaking engine change.
- UI: Dicts/FTS progress bars unchanged visually.