## 1. Pin the current behaviour with a failing check

- [x] 1.1 In `carve/smoke/main.cpp`, after the scan, resolve each loaded dictionary's index path and fail the run if any of them is not inside the index directory the tool was given, printing the offending path (design.md D4)
- [x] 1.2 Run the smoke tool with the current code and confirm the new assertion **fails**, and that the reported path is `<cfg><md5>` — this is the bug reproduced before it is fixed. Ran before touching `gd_init`: all three dicts reported `INDEX_PLACEMENT=FAIL missing index for <id> at <cfg>/index/<id>`, while the real indexes were at the `<cfg>/index<id>` siblings (`indexc9ab98b4…`, `index18f6d0bc…`, `index3f48fc8d…`, `index3f48fc8d…_FTS_x`) and `cfg/index/` was empty — the same shape the device showed (`files/index/` empty, `index<md5>` beside it)
- [x] 1.3 Record the command and the failure output in this change. Command: `aurelex_smoke.exe <cfg> <dic> smoke` after generating the fixtures with `scripts/make-smoke-stardict.py` and `scripts/make-example-dicts.py`; output recorded in 1.2 above

## 2. Boundary: enforce the prefix contract

- [x] 2.1 In `gd_init` (`carve/gd_boundary.cc`), append a path separator to the stored `indexDir` when the caller did not supply one — via the shared `gdNormalizeIndexDir` in `carve/index_path.hpp` (design.md D1)
- [x] 2.2 Reject an empty or separator-only `index_dir` with a distinct return code (`-2`) instead of normalizing it into a root-relative path (design.md Risks)
- [x] 2.3 Do not double the separator when the caller already supplied one, and accept both `/` and `\` as existing separators (design.md Risks)
- [x] 2.4 Document the trailing-separator contract and the `-2` return on `gd_init` in `carve/goldendict.h`
- [x] 2.5 Confirm no `gd_*` signature changed (`git diff carve/goldendict.h` is comments only; `int gd_init(const char*, const char*)` unchanged) and no unpatch edit under `engine/` (submodule delta is still exactly the three files' worth in `patches/`, which reverse-apply cleanly)

## 3. Callers

- [x] 3.1 Build the app's index path with `QDir::filePath("index")` plus a trailing separator in `EngineController::initialize`, instead of `appDir + "/index"` (design.md D2)
- [x] 3.2 Change the smoke tool to pass `<configDir>/index/` as its index directory instead of reusing the config directory (design.md D3)
- [x] 3.3 Create the `index/` subdirectory in `.github/workflows/engine-smoke.yml` alongside the existing `cfg` directory, and gate CI on `INDEX_PLACEMENT=OK`

## 4. Verify

- [x] 4.1 Re-run the smoke tool and confirm the assertion from 1.1 now **passes** — `INDEX_PLACEMENT=OK (index dir …/cfg/index, 3 dicts)`, `cfg/index/` now holds the bare dictionary ids and there are no `index*` siblings; the full run reports 14 `=OK`, 0 `=FAIL`
- [x] 4.2 Unit test that a path already ending in a separator is not doubled, and that a path without one is normalized exactly once — `app/tests/IndexMigrationTest.cpp` (`index_migration_test`), covering no-separator, `/`, `\`, and an already-doubled separator; passes
- [x] 4.3 Confirm the full CI smoke workflow passes, including the new containment assertion — the workflow now greps `INDEX_PLACEMENT=OK`; the local equivalent run is green (14 OK / 0 FAIL). CI itself runs on push
- [x] 4.4 Confirm lookup still works end to end after the path change — on device, after the migration the app searched a headword and rendered the article with its embedded resources, so the indexes in the corrected location were found (no reindex)
- [x] 4.5 On device, after the change: `files/index/` is non-empty and holds entries whose names are **bare dictionary ids** (no `index` prefix), and no `index<md5>` siblings remain beside it — confirmed on the ThinkPhone: `ls files/index` shows `008c9d6a…`, `008c9d6a…_FTS_x`, … and the sibling count is 0

## 5. Migrate existing devices (Option A: move in place — design.md Migration Plan)

- [x] 5.1 Sweep the app directory before `gd_init` and move each entry matching `^index([0-9a-fA-F]{32}(_FTS_.*)?)$` from `index<rem>` to `index/<rem>` via `QDir::rename` (handles the `_FTS_*` companion directories too) — `app/IndexMigration.hpp`, called from `EngineController::initialize`
- [x] 5.2 When the destination already exists, remove the source instead of skipping, so the strays do not leak; leave the source in place if the rename fails, and continue rather than aborting startup — covered by the `existing-destination` test case
- [x] 5.3 Make it idempotent — a second launch finds no matches and is a no-op — covered by the `second pass is a no-op` test case, and by the device run once the strays were gone
- [x] 5.4 Add a test with the three cases: a plain `index<md5>`, an `index<md5>_FTS_x` directory, and a non-matching `index.txt` that must be left alone — `app/tests/IndexMigrationTest.cpp`, all cases pass
- [x] 5.5 Confirm on device that the strays are gone, so `gd_remove_dict` deletes the real index rather than leaking it — the device logged `migrated 77 stray index entries into index/` (matching the 77 pre-count) and the sibling count is now 0, so a removal unlinks the real index

## 6. Housekeeping

- [x] 6.1 Confirm `patches/` is unchanged — `git status -- patches` is empty (design.md Non-Goals)
- [x] 6.2 Note the index layout change in `docs/ROADMAP.md` (the path moves and the strays are migrated in place)
