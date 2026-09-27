## Why

Every dictionary backend builds its index path by raw string concatenation — `string indexFile = indicesDir + dictId;` in all 18 of them (`engine/src/dict/dsl.cc:1752`, `mdx.cc:1476`, `stardict.cc:1920`, and so on) — which only produces a path inside the index directory if `indicesDir` already ends in a separator. Upstream knows this and satisfies it: `Config::getIndexDir()` returns `result.path() + QDir::separator()` (`engine/src/config.cc:2212`). Neither of our two consumers honours that contract, because the carve's `gd_init` stores the caller's string verbatim (`carve/gd_boundary.cc:379`) and both callers pass a bare directory path with no trailing separator.

The app creates `files/index/`, then tells the engine to write indexes there, and the engine writes them *next to* it. Device evidence on 2026-09-27: `files/index/` exists and is empty, while ~40 index files sit beside it as `index<md5>` siblings, each paired with an `index<md5>_FTS_x` directory. The smoke tool is worse — it passes its config directory as the index directory (`carve/smoke/main.cpp:76`), so CI writes its indexes as `$RUNNER_TEMP/cfg<md5>`, scattered into the parent of the directory it was given. CI never noticed, because it asserts on article HTML and never on where indexes land.

`files/index<md5>` is a *sibling* of the `index/` directory, not a file inside it, so the directory the app creates for indexes is dead weight that looks authoritative. Any future code that reasons about the index directory — a cache wipe, a backup, a size check, a subdirectory layout — will silently operate on the wrong path. The smoke tool's variant is already writing outside its sandbox, which is the failure mode that will bite first.

The fix is not a pure refactor: correcting the separator changes where every existing device looks for its indexes, so the change also migrates the ~40 strays in place — a startup sweep moves `index<md5>` to `index/<md5>` (and its `_FTS_*` companions), so no dictionary has to be reindexed. See Migration Plan in `design.md`. Shipping the fix without the migration would leak the strays and force a full reindex on every device.

## What Changes

- **Normalize the index directory at the boundary.** `gd_init` appends a path separator when the caller's `index_dir` lacks one, so the documented contract is enforced once, at the place that consumes it, and no future caller can get it wrong by accident.
- **Correct the app to pass a well-formed path.** `EngineController` builds the index path with `QDir` and a trailing separator rather than string concatenation, so it is correct independent of the boundary's tolerance.
- **Give the smoke tool its own index subdirectory** instead of reusing the config directory, so CI exercises the same layout the app does and its indexes stop landing outside the directory it was handed.
- **Assert index placement.** The smoke run fails if a dictionary's index is not created inside the index directory, so this cannot regress silently again. The assertion is the part with lasting value: it converts an invisible path bug into a build failure.

No engine change. The concatenation in the 18 backends is upstream's documented contract, not a defect, so `patches/` is untouched and AGENTS.md golden rule 1 holds.

## Capabilities

### Modified Capabilities

- `dictionary-management`: "Index build and validation on device" currently requires that an index be built, validated, and rebuilt when stale, but says nothing about *where* the index lives. It gains a containment guarantee — a dictionary's index is written inside the app's index directory, and no index is written outside it — plus the scenarios that make the smoke assertion and the cleanup path testable.

## Impact

- `carve/gd_boundary.cc` — `gd_init` normalizes the stored `indexDir`; documented in `carve/goldendict.h` where the trailing-separator requirement is currently implicit.
- `app/EngineController.cpp:587` — index path built via `QDir` with a trailing separator.
- `carve/smoke/main.cpp:76` — uses a dedicated `index/` subdirectory under the config dir.
- `carve/smoke/main.cpp` — new post-scan assertion that every built index resolves inside the index directory.
- `.github/workflows/engine-smoke.yml` — create the `index/` subdirectory alongside `cfg`; the new assertion now guards the smoke step.
- `openspec/specs/dictionary-management/spec.md` — updated to match.
- `app/` — no change to what the user sees, but a real change to the on-disk index layout: every device's indexes move from `files/index<md5>` to `files/index/<md5>`. The chosen migration (design.md Migration Plan) ships in the same release as the fix; this bullet is rewritten because the earlier version here claimed the strays "stay valid in place", which is false.
