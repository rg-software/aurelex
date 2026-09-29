## Context

See `proposal.md` for motivation. Two constraints from the repo shape every
decision below:

- The engine is upstream (`engine/`, pinned tag) and is **never edited in
  place**; deviations live in `patches/` and must survive the patch pipeline
  and CI smoke test (AGENTS.md golden rule 1).
- The only app<->engine channel is the `gd_*` C boundary (`carve/`). The app
  already drives FTS from one QtConcurrent worker (`EngineController::
  ensureFtsWorker`) and already addresses dictionaries by **stable id**, not
  engine index, when it matters.

Current facts that constrain the design:
- `gd_fts_index` holds `g_engineMutex` for the whole `makeFTSIndex()` call
  (`carve/gd_boundary.cc:1269`), so every lookup, search, scan, group edit, and
  removal blocks for the build's whole duration. The UI stays responsive —
  lookups run on a worker pool (`app/EngineController.cpp:1577`) — but *no*
  dictionary can be used while any dictionary indexes.
- `FtsHelpers::makeFTSIndex` commits only once, after the whole loop, then
  `db.compact(final)` (`engine/src/ftshelpers.cc:166,169`) — a single
  end-commit plus a full second rewrite. The resume logic at lines 102-129 is
  dead because nothing is ever committed before the end.
- Article reads are only *partially* internally locked, so concurrent engine
  access is not something the code makes obviously safe: `loadArticle` locks
  `idxMutex` around the mmap/decompress block (`engine/src/dict/mdx.cc:888-901`)
  but the chunk lookup just above it is left unlocked (the `QMutexLocker` at
  mdx.cc:879 is commented out), and `setIndexedFtsDoc` writes a plain `long`
  and emits a signal with no atomic (`engine/src/dict/dictionary.cc:225-234`).
- `QAtomicInt isCancelled` is created and passed to `makeFTSIndex` but never
  set (`carve/gd_boundary.cc:1289`) — cancellation does not exist.
- `gd_remove_dict` takes `g_engineMutex` and takes an engine index; the QML
  Remove button and `removeDictionary` are gated on `processingActive`.
- `gd_dict_meta` already returns `size_bytes`, so the app can bound auto-FTS by
  dictionary size without new boundary surface.
- `ArticleMaker::makeDefinitionFor` already accepts a `mutedDicts` set keyed by
  dictionary id (`engine/src/article_maker.hh:45`, matched at
  `engine/src/article_maker.cc:339-348`), so an in-flight dictionary can be
  withheld from lookup with **no engine change**.

## Goals / Non-Goals

**Goals:**
- While an FTS build runs, ordinary lookups, full-text searches, scans, group
  edits, and removal SHALL work on every dictionary **except** the one being
  built.
- Any single operation SHALL wait at most **one indexing slice** for the build;
  slice length is bounded by wall clock, not by dictionary size.
- Engine access stays **mutually exclusive** — never two threads in the engine
  at once.
- An interrupted build resumes from persisted progress; peak build memory is
  independent of total dictionary size.
- The import chain does not auto-build a dict so large that the build would
  dominate it; that dict is built on first full-text search.
- Dictionary removal works during staging / scanning / indexing, safely.

**Non-Goals:**
- Parallel builds across multiple dictionaries (single FTS worker stays).
- Concurrent (lock-free) engine access — the build is *interleaved*, not
  parallel.
- Changing the xapian dependency/version or the on-disk FTS schema.
- Pre-built desktop-generated index caches (separate proposal).
- Any user-visible English string change (no RU/JA catalog work).

## Decisions

### D1 - Interleave the build: release the lock for one bounded slice at a time
`gd_fts_index` no longer holds `g_engineMutex` across the whole
`makeFTSIndex()`. The boundary registers a **yield hook** (`FtsHelpers::
setYieldCallback`) and calls `makeFTSIndex()` once; the engine calls the hook
every bounded wall-clock slice (`kSliceBudgetMs`), and the hook briefly releases
`g_engineMutex` (then reacquires before the build touches the engine again).
Access to the engine therefore remains mutually exclusive — no two threads are
ever in the engine at once — but waiting operations (lookups, searches, scans,
group edits, removal) get the lock in between slices. Slice length is bounded by
wall clock, not document count, so the maximum wait any operation sees is one
slice regardless of dictionary size. The build's own state (the target `sptr`
and its sorted offset list) is captured once and touched only by the build
thread.

*Alternatives:* (a) release the lock for the whole build and let lookups run in
parallel (the previous design's D1) — rejected: it depends on the engine
tolerating concurrent article reads, which the code does not make obviously
safe, and this change prioritises safety over convenience; (b) a re-entrant
per-slice call (return after N docs and re-invoke) — rejected: it recomputes
`findArticleLinks` on every slice, an O(N)-per-slice cost that grows with the
number of slices; (c) per-dictionary locks — rejected: `g_state`, groups, and
`ArticleMaker` remain shared, so a lookup still needs the global lock;
per-dictionary locks add lock-ordering risk without removing the global one.

### D2 - The dictionary being built is withheld from lookup and FTS
While a build is in flight for dictionary id `I`, `gd_lookup` and
`gd_lookup_in_group` pass `{I}` as `ArticleMaker::makeDefinitionFor`'s
`mutedDicts` (an existing parameter keyed by dictionary id), and `gd_fts_search`
already omits dictionaries without a complete index. The in-flight id is a
file-static guarded by `g_ftsProgressMutex`. The exclusion is keyed on **"build
in flight"**, NOT on **"index missing"**: a loaded dictionary with no index
that is not currently building (deferred, queued, or holding a failed/cancelled
build) stays fully usable for ordinary lookup. This is behavior-preserving:
today the global lock makes the whole engine — including `I` — unusable during
a build, so withholding only `I` costs the user nothing they had.

*Alternative:* withhold on "no index" — rejected: it would make deferred and
not-yet-built dictionaries unusable for headword lookup, a real regression.

### D3 - Periodic commit and yield inside one build call; atomic publish
Patch `FtsHelpers::makeFTSIndex` to (a) commit every `kCommitEvery` documents
and (b) call the yield hook every `kSliceBudgetMs`, both independent of each
other (a yield may release the lock with uncommitted documents; the `_temp`
database is private to the build thread, so that is safe). Committing
periodically bounds peak memory and makes the existing `lastdocid` resume path
(`ftshelpers.cc:102-129`) genuine: an interrupted run continues from the last
committed document. The final `finish_mark` document remains the completion
signal, so `ftsIndexIsOldOrBad` / `haveFTSIndex` behave unchanged.

Finalize by `db.close()` then an **atomic publish** of the committed `_temp`
directory to `ftsIndexName()` under a brief lock, instead of the trailing
`db.compact(final)`: `compact()` is a full second pass that would otherwise
have to hold the lock across the whole rewrite, defeating the bounded-slice
goal. Rotate any stale final aside before the move (the existing final is
already stale — `gd_fts_index` only runs when `haveFTSIndex()` is false), and
recover a `_temp` that already carries `finish_mark` (a build killed between its
final commit and the publish) by publishing it instead of rebuilding.

*Alternatives:* (a) keep `db.compact(final)` — rejected as the default because
of the long locked stall, but retained as a **fallback** inside `publishIndex`
if the rename fails; (b) commit to the final path directly — rejected: loses
the `_temp`/final separation that makes resume detectable.

### D4 - Cancellation and id-keyed removal: a flag plus a bounded wait
Replace the never-set `isCancelled` with a file-static cancel token under
`g_ftsProgressMutex`, keyed by the id of the build in flight. Add
`gd_fts_cancel(const char *dict_id)` (arms the token when the id matches the
in-flight build) and `gd_fts_build_state(const char *dict_id, int *out)`
(idle vs building) to `carve/goldendict.h` and its implementation. The build
checks the token at each slice boundary and aborts through the existing path
that removes `_temp`.

Because engine access is serialized, removal is a **bounded sequence, not a
cross-thread handshake**: (1) the app drops the id from the FTS queue and calls
`gd_fts_cancel(id)`; (2) it waits, bounded (a couple of slices), for
`gd_fts_build_state(id) == idle`; (3) it calls `gd_remove_dict(index)` and
reaps files. If the wait expires, the file reap is deferred to the FTS worker's
completion callback. The serialized execution gives the same ordering guarantee
the previous design needed a confirm-idle/reap protocol for, without the token
address dance.

*Alternatives:* (a) let the worker finish then delete — rejected: a huge dict
would delay removal for minutes; (b) delete immediately and rely on the build
failing — rejected: racy, can recreate index files after reaping.

### D5 - Bound auto-FTS by size; build deferred dicts on demand
`autoIndexMissing` skips dictionaries whose `gd_dict_meta` `size_bytes` exceeds
a threshold (`kAutoFtsMaxBytes`), leaving them without a build and marking them
deferred. `ftsSearch` detects scoped dictionaries that lack an index, enqueues
on-demand builds through the same single FTS worker, and returns results from
the already-indexed dictionaries immediately; when an on-demand build completes
(`ftsIndexChanged`), the controller re-runs the pending query so the deferred
dictionary's hits appear. This keeps upstream's `maxDictionarySize = 0` (which
would make a large dict permanently non-FTS-able) untouched and preserves the
spec's "searchable as its index completes".

*Alternatives:* (a) reuse `maxDictionarySize` — rejected: binary exclusion, not
deferral; (b) make FTS fully manual for all dictionaries — rejected: changes the
automatic-bulk behavior the spec retains for normal-size dictionaries.

### D6 - Verify the lookup-index cache before attributing cost (diagnostic)
Before optimizing further, confirm from existing logs that `gd_scan_dicts took
%lld ms` is small on relaunch. `indexIsOldOrBad` compares exact mtimes
(`engine/src/dict/mdx.cc:1431`); if Android re-stamps staged files, the main
btree index rebuilds every launch and that — not FTS — is the real cost. This
is a task, not a code change, and it can invalidate the priority order.

## Risks / Trade-offs

- Every operation can wait up to one slice for the build -> bounded by a
  wall-clock budget (`kSliceBudgetMs`); this is the deliberate
  safety-over-convenience trade. If the stall still proves annoying, the next
  increment is fine-grained locking — hold `g_engineMutex` only around
  `dict->getArticleText` and let folding / `index_text` run unlocked — which
  keeps dictionary access mutually exclusive while shrinking the window.
- The dictionary being built is absent from lookup and FTS while it builds ->
  by design and behavior-preserving (today it is unavailable too).
- No data races by construction; the residual risk is *logic* (cancel timing,
  publish ordering), which is deterministic and testable rather than flaky.
- The bounded/resumable build contract lives in a patch -> patch pipeline + CI
  smoke (AGENTS.md); keep the patch minimal (work budget, commit cadence,
  atomic publish, cancel honor).
- The atomic publish could leave a missing final if killed mid-move -> rotate
  the old final aside first and reconcile on startup; fall back to `compact()`.
- Cancel + reap ordering is the sharpest logic edge -> now a single
  thread-at-a-time sequence, exercised by a removal test during an active
  build.
- `gd_cleanup` could free `g_state` between slices -> it must wait for an
  in-flight build; the app does not currently call it, so this is a documented
  boundary invariant plus a guard.
- On-demand builds can surprise a user with a long first FTS search -> show the
  per-dictionary building state and keep results from indexed dictionaries.
- D6 may show the main-index cache, not FTS, dominates -> if so, fix that first
  and rescope the FTS work.
- Only one build per dictionary may be in flight -> the app's single FTS worker
  enforces this; note it as a boundary invariant.

## Migration Plan

No data migration. On first run after upgrade, existing complete FTS indexes are
reused (they still carry `finish_mark`); a `_temp` left by an interrupted build is
resumed or discarded by the existing `_temp`/final logic. Rollback = revert the
boundary changes and drop the engine patch; no on-disk format changed, so
existing indexes keep working.

## Open Questions

- Exact `kAutoFtsMaxBytes` default (order of a few hundred MB?) — tune on a
  device with a real large dictionary; the approach and specs do not depend on
  the value.
- `kSliceBudgetMs` (and whether the commit cadence equals the slice boundary or
  is coarser) — correctness is independent of both; tune for stall latency vs
  commit overhead.
