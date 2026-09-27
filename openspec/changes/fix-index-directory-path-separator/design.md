## Context

The engine treats `indicesDir` as a **prefix**, not as a directory. All 18 backends compute `string indexFile = indicesDir + dictId;` — `dsl.cc:1752`, `mdx.cc:1476`, `stardict.cc:1920`, `aard.cc:770`, `epwing.cc:1161`, `zim.cc:801`, and the rest — with no separator inserted. Upstream is consistent with that: `Config::getIndexDir()` returns `result.path() + QDir::separator()` (`engine/src/config.cc:2212`), appending the separator by hand precisely because nothing downstream will.

The carve is the gap. `gd_init` takes `index_dir` from the caller and stores it verbatim (`carve/gd_boundary.cc:379`), so it inherits a contract that `carve/goldendict.h` documents only by implication. Two callers then get it wrong in the same way:

| Caller | Passes | Resulting index path | Actual location |
|---|---|---|---|
| `EngineController.cpp:587` | `<appDir>/index` | `<appDir>/index<md5>` | beside the directory |
| `smoke/main.cpp:76` | `<configDir>` | `<configDir><md5>` | outside the directory |

The app creates the directory (`QDir().mkpath(indexDir)`), so `files/index/` exists and is permanently empty while ~40 real indexes sit beside it. The smoke tool passes its config directory *as* the index directory, so CI scatters indexes into the parent of the directory it was given.

**These are different paths, and the difference is the whole bug.** `files/index<md5>` is a *sibling* of the `index/` directory; `files/index/<md5>` is a file *inside* it. Fixing the separator does not relocate the existing files — it makes the engine stop looking where they are. Concretely, after the fix every device reindexes from scratch, and the strays at `files/index<md5>` are never read or removed again, because `gd_remove_dict` will only unlink the path it now computes. That is a real upgrade cost and a slow disk leak, so it is a decision to make deliberately rather than a detail to wave through. See Migration Plan.

## Goals / Non-Goals

**Goals:**

- Enforce the prefix contract once, at the boundary, so no caller can violate it by accident.
- Make the app's own path correct without depending on that tolerance.
- Give CI an index directory distinct from its config directory, matching the app's layout.
- Turn index placement into something a build fails on, rather than something a human notices.

**Non-Goals:**

- Any engine change. The concatenation is upstream's documented contract; patching 18 backends to insert separators would be a large deviation for a latent bug (AGENTS.md golden rule 1 and "keep patches small").
- A cache-wipe or index-pruning *feature*. This change only makes the existing directory trustworthy enough for one to be built on later. The one-time handling of the strays is in scope only as far as Migration Plan requires.
- Changing the index file naming scheme, which is upstream's (an MD5 of the dictionary file list, `dictionary.cc:562`). Note the strays carry an extra `index` prefix that is an artifact of the bug, not part of the scheme, so anything that moves them must strip it.

## Decisions

### D1: Normalize in `gd_init` — the boundary owns the contract

`gd_init` appends a separator to the stored `indexDir` when one is absent, and documents the requirement in `carve/goldendict.h`.

Rationale: this is the only place that knows the engine's contract, and it is ours to enforce (AGENTS.md golden rule 3 — the boundary is the C API). Fixing only the two callers leaves the next caller — a future headless tool, a test, the release smoke run — one line away from the same silent failure, and nothing in the type system or a comment will catch it. Normalizing costs three lines and makes the tolerance permanent rather than tribal knowledge.

*Alternatives considered.* Fix both callers and document the requirement. Rejected as the primary fix: it treats a boundary precondition as caller folklore, and the smoke tool already demonstrates how easily that is lost. Accept the current behaviour and do nothing. Rejected: it leaves a directory the app creates for indexes empty and unusable, which is a trap for the next feature.

### D2: The app builds its path with `QDir`, not concatenation

`EngineController` constructs the index path via `QDir::filePath("index")` plus a trailing separator.

Rationale: correctness by construction, and independent of D1. The two fixes are complementary rather than redundant — D1 is the guard, D2 is the caller being correct. If someone later removes D1, D2 still holds the app steady, and the smoke assertion (D4) catches the regression.

### D3: The smoke tool gets its own `index/` subdirectory

`carve/smoke/main.cpp` passes `<configDir>/index/` instead of reusing `configDir`.

Rationale: it mirrors the app's layout, so CI exercises the same shape as production, and it stops CI writing outside the sandbox it was given. Reusing the config directory was a shortcut that happened to work only because the app's own path was equally wrong — the two defects were masking each other.

### D4: Assert containment in the smoke run

After the scan, the smoke tool resolves each built dictionary's index path and verifies it is inside the index directory it was given; any escape fails the run with a clear message.

Rationale: this is the part of the change that pays for itself. The bug survived because every consumer was wrong in the same direction and nothing checked the result. An assertion converts a class of invisible path bug into a build failure, and it will catch the next caller that gets this wrong — including any future change to how the index directory is computed.

*Alternative considered.* Assert only that the index directory is non-empty. Weaker: it would pass today with any other file in it, and would not catch a single misdirected index. Containment is the actual invariant.

## Risks / Trade-offs

**[Risk] Normalizing a path that already ends in a separator must not double it.** A doubled separator is harmless on POSIX and Windows, but it makes log lines and assertions noisy, and `files/index//<md5>` reads as a defect. *Mitigation*: check for a trailing separator before appending, and assert the normalized form in a unit test.

**[Risk] An empty or relative `index_dir` is normalized into something surprising.** A caller passing `""` would get a bare separator, and the engine would write to the filesystem root. *Mitigation*: reject an empty `index_dir` in `gd_init` with a distinct return code rather than normalizing it into a root-relative path. The current code has no such check; adding it is in scope because normalization is what makes the empty case reachable in a new way.

**[Trade-off] This is a live data-layout change, not a pure refactor.** Fixing the separator invalidates every index path on every existing device. *Mitigation*: Migration Plan migrates the strays in place (Option A) rather than assuming they "stay valid", which was the earlier and wrong assumption in this document. The migration ships in the same release as the fix — shipping one without the other would leak the strays and force a full reindex.

**[Trade-off] Tolerating a missing separator hides caller mistakes.** A stricter boundary could reject instead of normalizing, forcing callers to be right. Rejected: it converts a benign, well-understood tolerance into a runtime failure at startup for a condition that has one correct fix and no security implication. The D4 assertion covers the case where the tolerance would matter.

## Migration Plan

**Decision (Option A): migrate the strays in place.** On startup, before `gd_init`, sweep the app directory and move each stray index into the corrected `index/` subdirectory, stripping the artifact `index` prefix.

A dictionary's index id is an MD5 (32 hex chars), and the engine writes `dictId` plus optional `_FTS_*` companions. So an entry is a stray iff its name matches `^index([0-9a-fA-F]{32}(_FTS_.*)?)$` — the capture is exactly the destination basename. The `index/` directory itself does not match (nothing follows `index`), and neither does an unrelated file like `index.txt`, which is why the shape is checked rather than a bare `startsWith("index")`.

For each match `index<rem>`:
- dest = `<appDir>/index/<rem>`;
- if dest does not exist, `QDir().rename(src, dest)`;
- if dest does exist, remove `src` — `dest` is the corrected path and is authoritative, and leaving `src` would keep the leak this change exists to stop.

The sweep is naturally idempotent: after a successful pass no entry matches, so a second launch is a no-op. It runs on the app-private `files/` tree only, so there is no permission or SAF concern.

Why A over "discard and let the engine rebuild": a rebuild is self-healing but forces every dictionary to reindex after the upgrade — minutes of background work on a phone with ~40 dictionaries — for data that is already valid and merely one directory away. The move is bounded code, and the shape check keeps it from touching anything it did not create.

Items that need care:
- Move the `_FTS_*` companions with the index, not just the index file; a dict whose index moved but whose FTS directory did not would silently lose full-text search until reindexed.
- Use `QDir::rename`, not `QFile::rename`, since these include directories.
- A rename can fail (e.g. a partially written file); on failure, leave the source in place and continue rather than aborting startup — the engine will simply rebuild that one on next scan.

Device verification: after the upgrade, `files/index/` is non-empty and holds entries whose names are bare dictionary ids (no `index` prefix), and no `index<md5>` siblings remain beside it.

Rollback is a revert, but note that migration is a destructive move: after it has run, reverting the code leaves the indexes in the new location, where the old code will not find them and the strays no longer exist to be picked up. A rollback therefore implies a reindex.

## Open Questions

None. The migration option is decided (A — move in place, above), and the containment invariant, fix location, and assertion were already decided.
