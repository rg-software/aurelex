## Context

See `proposal.md` — Why for the defect and its severity.

The relevant current state:

- `gd_dict_info( index, name, name_size, file, file_size )` (`carve/gd_boundary.cc:904`)
  returns `-1` when the name does not fit `name_size` (`:916`) or the source path does not
  fit `file_size` (`:924`). It refuses rather than truncating. `file_size` is a **caller**
  parameter.
- The app reads a source path in exactly two places, both with fixed buffers:
  `readDictInfoAt()` uses `char name[256]` / `char file[512]`
  (`app/EngineController.cpp:421-422`) and the FTS indexing loop uses `nb[256]` / `fb[512]`
  (`:704`).
- `readDictInfoAt()` is the single pinhole both consumers go through: the QML model
  (`refreshDictionaries()`, `:867`) and the scan's in-use set (`:475`). An entry it cannot
  name is therefore dropped from both, which is why the defect is invisible *and*
  unmanageable.
- `gd_dict_info` requires a non-null `file` buffer whenever `file_size > 0` (`:906`), so a
  caller that only wants the name cannot opt out by passing `nullptr, 0`.

## Goals / Non-Goals

**Goals**

- Every dictionary the engine loaded is listed, and therefore removable.
- No change to the boundary API, the engine, or `patches/`.
- No change to when the staged sweep may delete a directory. This change must not be a
  route back to the deletion that `fix-stale-sweep-deletes-live-dictionaries` fixed.

**Non-Goals**

- The reported-failure branch (`sweepStaleStagedDirs`'s `m_scanFailures` path) stays as
  found; it is owned by `report-import-results`.
- No new UI, no "repair" affordance, and no change to the Dicts list's presentation.
- Not revisiting the fixed-buffer pattern itself; the buffers stay fixed and stack-allocated,
  only larger.

## Decisions

### D1: Fix at the app's pinhole, not the boundary

The refusal is caused by a size the app chooses, so the app is where it is corrected.
Alternatives considered:

- **Widen or replace `gd_dict_info`** so it returns a length or a heap string. Rejected: it
  changes a C ABI shared by the app and the CI smoke tool for no benefit, when the API
  already lets the caller ask for as much as it wants.
- **Truncate the path instead of refusing it.** Rejected, and worth recording because it
  looks harmless: a truncated path is *wrong* data, not merely incomplete. The sweep's
  containment and sharing tests compare paths by prefix
  (`StagedCleanup::isUsedByLoadedDictionary`), so a truncated source could match a
  *different* staged directory and protect the wrong one — or protect none. Refusing is
  safe; truncating is not.

### D2: `PATH_MAX` as the buffer size, shared by name and path

`PATH_MAX` (4096 on Android) is the largest path a conforming filesystem accepts, so any
path that can exist fits, and there is no arbitrary magic number to outgrow. Two buffers
that must agree (name and path) are sized from one constant so they cannot drift, as they
did between the two call sites.

A larger name buffer costs nothing here and closes the same class of defect for a
pathologically long dictionary *name*, which the same `:916` check would otherwise refuse.

Stack cost is 4096 bytes per call against 512 — one call at a time, off the main thread, on
a path that already allocates a `QString` per dictionary. Not a concern.

### D3: The sweep's retention rule is untouched

Completeness of the in-use set improves what the sweep *knows*, but the rule that a directory
holding a primary dictionary file is retained stays exactly as it is. It is tempting to treat
"loaded but unlisted" as an argument for letting the sweep reclaim such a directory; that
would delete live data, which is the defect this work follows. The dead end is cured by
making the dictionary listable, not by making it deletable behind the user's back.

## Risks / Trade-offs

- **[A path longer than `PATH_MAX` is still dropped]** → Unchanged from today's behaviour, so
  this is strictly an improvement and never a regression: no input that works now stops
  working. Android's filesystem cannot produce such a path anyway.
- **[The fix cannot be proven without a rebuild]** → The *defect* is already proven on device
  (530-byte path loaded but unlisted; 500-byte sibling listed). Confirming the *fix* needs one
  build-and-verify cycle with a long-path fixture, which the tasks cover; until then the
  change is verified on the host only.
- **[Bumping the FTS loop's path buffer looks pointless because it never reads it]** → It
  passes `fb` only to satisfy the API's non-null requirement, so the buffer is unused; a
  reader might be tempted to drop it, which `gd_dict_info:906` makes impossible. Comment it
  where it is sized.

## Migration Plan

None. No persisted state, no schema or layout change, and no behaviour change for any user
whose staged paths already fit the current buffers. Rollback is a plain revert.

## Open Questions

- **Should a loaded-but-unenumerable dictionary be reported rather than silently dropped?**
  Deferrable: with the buffers at `PATH_MAX` the case cannot arise from file length, and the
  spec's completeness requirement is satisfied without it. Worth revisiting only if the
  boundary ever gains a path source that is not a filesystem path.

## Supersedes the long-path caveat in `fix-stale-sweep-deletes-live-dictionaries`

That change's Open Questions record the fixed 512-byte path buffer as "a latent
defect, left as found" — a dictionary at a ≥512-byte staged path is loaded but
omitted from the model and the in-use set. **This change fixes exactly that
defect**, so once both are archived the older note must be read as describing the
state *before* this change, not a still-open issue. The older note is otherwise
consistent with this one: it reaches the same conclusion (raise the two caller
buffers to `PATH_MAX`; no boundary, `patches/` or engine edit) and the same
byte-vs-character observation. What it left open — whether a loaded-but-
unenumerable dictionary should be *reported* — stays open here too (see Open
Questions), because at `PATH_MAX` the case can no longer arise from path length.
