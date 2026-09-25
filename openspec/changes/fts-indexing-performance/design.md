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
  (`carve/gd_boundary.cc:1096`), so lookups/search block behind it.
- `FtsHelpers::makeFTSIndex` calls `db.commit()` once, after the whole loop,
  then `db.compact(final)` (`engine/src/ftshelpers.cc:166,169`) — a single
  end-commit plus a full second rewrite. The resume logic at lines 102-129 is
  dead because nothing is ever committed before the end.
- `QAtomicInt isCancelled` is created and passed to `makeFTSIndex` but never
  set (`carve/gd_boundary.cc:1116`) — cancellation does not exist.
- `gd_remove_dict` takes `g_engineMutex` and takes an engine index; the QML
  Remove button and `removeDictionary` are gated on `processingActive`.
- `gd_dict_meta` already returns `size_bytes`, so the app can bound auto-FTS by
  dictionary size without new boundary surface.

## Goals / Non-Goals

**Goals:**
- A running FTS build must not block lookups, scans, group edits, or removal.
- An interrupted build resumes from persisted progress; peak build memory is
  independent of total dictionary size.
- The import chain does not auto-build a dict so large that the build would
  dominate it; that dict is built on first full-text search.
- Dictionary removal works during staging / scanning / indexing, safely.

**Non-Goals:**
- Parallel builds across multiple dictionaries (single FTS worker stays).
- Changing the xapian dependency/version or the on-disk FTS schema.
- Pre-built desktop-generated index caches (separate proposal).
- Any user-visible English string change (no RU/JA catalog work).

## Decisions

### D1 - Build off the engine lock; snapshot the target under it
`gd_fts_index` takes `g_engineMutex` only to resolve/snapshot the target
`sptr<Dictionary::Class>` and to read state, then **releases it before
`makeFTSIndex()`** and re-takes it only to publish results. The `sptr` keeps the
dictionary object alive if it is erased from `g_state->dictionaries` mid-build,
so removal/scan can proceed concurrently. The FTS progress slot moves out of
`g_state` to a file-static guarded by the existing `g_ftsProgressMutex`, so its
lifetime no longer depends on `g_state`. `gd_cleanup` (currently uncalled by the
app) must also wait for an in-flight build before deleting state; note this in
the boundary implementation.

*Alternatives:* (a) build on a `duplicate()` snapshot — rejected: writes the same
index path and adds no isolation over an `sptr`; (b) keep the lock and merely
lower poll frequency — rejected: does not restore search during a build.

### D2 - Periodic commit; replace `compact()` with an atomic rename
Patch `FtsHelpers::makeFTSIndex` to `db.commit()` every `kCommitEvery` (order
10k) documents, keeping the final `finish_mark` + commit as the completion
signal. Resume then genuinely works: an interrupted run finds the last committed
document's address in `_temp` and continues from `upper_bound(offset)`. Replace
the trailing `db.compact(final)` full rewrite with `db.close()` then an atomic
rename of the committed `_temp` directory to `ftsIndexName()`, removing any
stale final first. Xapian reads a committed writable database directory as a
normal database, so no conversion is required.

*Alternatives:* (a) keep `compact()` — rejected: a full second pass over the
whole index is exactly the cost this change targets; (b) commit to the final path
directly — rejected: loses the `_temp`/final separation that makes "is this index
complete?" checkable via `finish_mark` and makes resume detectable.

### D3 - Real, id-keyed cancellation; cancel -> confirm idle -> reap
Replace the never-set `isCancelled` with a file-static cancel token plus the id
of the build in flight, both under `g_ftsProgressMutex`. Add a boundary call
`gd_fts_cancel(const char *dict_id)` that arms the token when the id matches the
in-flight build; `makeFTSIndex` already polls `isCancelled` per article, and its
abort path removes `_temp`. Removal order becomes: (1) app drops the id from the
FTS queue and calls `gd_fts_cancel(id)`; (2) `gd_remove_dict(index)`; (3) file
reap (`deleteDictionaryFiles`) happens only after the engine reports no build
for that id (`gd_fts_build_state(id) == idle`), with a bounded wait, otherwise
deferred to the worker's completion callback. This prevents deleting an index
directory while the aborted build still holds it.

*Alternatives:* (a) let the worker finish then delete — rejected: a huge dict
would delay removal for minutes; (b) delete immediately and rely on the build
failing — rejected: racy, can recreate index files after reaping.

### D4 - Bound auto-FTS by size; build deferred dicts on demand
`autoIndexMissing` skips dictionaries whose `gd_dict_meta` `size_bytes` exceeds a
threshold (`kAutoFtsMaxBytes`), leaving them without a build and marking them
deferred. `ftsSearch` detects scoped dictionaries that lack an index, enqueues
on-demand builds through the same single FTS worker, and returns results from the
already-indexed dictionaries immediately; when an on-demand build completes
(`ftsIndexChanged`), the controller re-runs the pending query so the deferred
dictionary's hits appear. This keeps upstream's `maxDictionarySize = 0` (which
would make a large dict permanently non-FTS-able) untouched and preserves the
spec's "searchable as its index completes".

*Alternatives:* (a) reuse `maxDictionarySize` — rejected: binary exclusion, not
deferral; (b) make FTS fully manual for all dictionaries — rejected: changes the
automatic-bulk behavior the spec retains for normal-size dictionaries.

### D5 - Verify the lookup-index cache before attributing cost (diagnostic)
Before optimizing further, confirm from existing logs that `gd_scan_dicts took
%lld ms` is small on relaunch. `indexIsOldOrBad` compares exact mtimes
(`engine/src/dict/mdx.cc:1431`); if Android re-stamps staged files, the main btree
index rebuilds every launch and that — not FTS — is the real cost. This is a
task, not a code change, and it can invalidate the priority order.

## Risks / Trade-offs

- Removing `g_engineMutex` around the build exposes `g_state` to concurrent
  mutation -> mitigated by taking only an `sptr` snapshot and moving the progress
  slot out of `g_state`; the build touches no `g_state` member after snapshot.
- `gd_cleanup` could now free `g_state` mid-build -> it must wait for an
  in-flight build; the app does not currently call it, so this is a documented
  boundary invariant plus a guard.
- Replacing `compact()` with `rename()` could leave a non-compacted database ->
  smoke test opens the built index and searches it; if rename proves unreliable
  on a device, fall back to `compact()` behind the same periodic-commit change.
- Cancel/reap ordering is the sharpest edge -> the "cancel, then confirm idle,
  then reap" sequence is a single unit and must be exercised by a removal test
  during an active build.
- On-demand builds can surprise a user with a long first FTS search -> show the
  per-dictionary building state and keep results from indexed dictionaries.
- The engine patch can drift on an upstream bump -> patch pipeline + CI smoke
  (AGENTS.md); keep the patch minimal (commit cadence, rename vs compact, cancel
  honor already present).
- D5 may show the main-index cache, not FTS, dominates -> if so, fix that first
  and rescope the FTS work.

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
- `kCommitEvery` value — correctness is independent of it; tune for memory vs
  commit overhead.
