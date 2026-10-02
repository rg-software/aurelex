## 1. Widen the app's dictionary-info buffers

- [x] 1.1 Added one shared constant `kDictInfoBufferSize` (4096 — the value of
      `PATH_MAX` on Android) in `app/EngineController.cpp`, above `readDictInfoAt()`, with a
      comment recording why the size matters: `gd_dict_info` refuses a path that does not fit
      rather than truncating it, and a truncated path would be *wrong* data that the sweep's
      prefix comparison could match against a different staged directory. A `#ifndef PATH_MAX`
      fallback keeps the host tooling building.
- [x] 1.2 `readDictInfoAt()` now declares `char name[kDictInfoBufferSize]` /
      `char file[kDictInfoBufferSize]` (was 256/512), so the model and the sweep's in-use set
      are computed from the same, complete source paths.
- [x] 1.3 The FTS indexing loop's `nb` / `fb` use the constant too (was 256/512), with a
      comment there that `fb` is unused but cannot be dropped: `gd_dict_info` rejects a null
      file buffer whenever `file_size > 0`, so a caller that only wants the name must still
      supply one. The name-only fallback buffer in the FTS job builder (a heap
      `std::vector<char>`, was 256) is sized from the constant as well, so it cannot refuse a
      long dictionary *name* either.
- [x] 1.4 `static_assert(kDictInfoBufferSize >= PATH_MAX, ...)` added, so the buffer cannot
      silently shrink below a legal path again.

## 2. Verify

- [x] 2.1 Build the app (`app/build.ps1`) and the host test binary; confirm both compile and
      that the host suite still passes, with no behaviour change for paths that already fit
      the old buffers. **Done.** `ninja` rebuilt `EngineController.cpp.o` with only the two
      pre-existing warnings; the full Debug APK built and installed (`build.ps1 -Install`);
      and all eight `build-app-tests` executables exit 0.
- [x] 2.2 Recreate the long-path fixture on a debug device (the one used to prove the defect):
      two staged trees straddling the old 512-byte boundary, each holding a valid dictionary,
      one under and one over. Confirm the over-boundary dictionary is now **listed**, and that
      the Dicts list count matches `gd_dict_count` on a cold start. **Done** on the ThinkPhone
      (`ZY22HC8LTR`, Android 15, Debug). Two synthetic DSL fixtures with **unique** names were
      staged at absolute paths of 500 (`zzunder/…/under.dsl`, "ZZ Under Boundary") and 530
      bytes (`zzover/…/over.dsl`, "ZZ Over Boundary"); unique names matter because
      `resolve-duplicate-dictionaries` would otherwise collapse identical same-named copies. On
      a cold start: `gd_dict_count = 10`, `dictionaries available: 10`, and both rows appear in
      the Dicts list, including the 530-byte one. The earlier defect (a 530-byte path loaded but
      absent from the model) no longer reproduces.
- [x] 2.3 Remove the long-path dictionary through the Dicts list and confirm its staged copy
      and built index are deleted, that it stops appearing in lookups, and that its directory
      is reclaimed. **Done.** Selecting "ZZ Over Boundary" and tapping Remove logged
      `removeDictionary result: rc= 0 … remaining= 9`, then removed both index entries
      (`<id>` and `<id>_FTS_x`) and the staged `…/zzover/…/over.dsl`, and
      `removing staged dir "…/staged/zzover"`; the directory is gone. A lookup for
      `zzoverword` reports "not found" while `zzunderword` still resolves from
      "ZZ Under Boundary", so only the removed dictionary was affected.
- [x] 2.4 Re-confirm the two behaviours that must not regress, per `docs/TESTING.md` rows 8k
      and 8l: a nested import still survives a restart, and a genuinely empty leftover staged
      directory is still reclaimed. **Done**, both in one cold start: the sweep reported
      `in-use sources handed to the sweep = 9` and `485ea40a` survived with no reclaim for it,
      and `thank you` still resolved from **Aurelex Phrasebook** (the nested import, row 8k);
      a hand-made `staged/emptyleftover/leftoversub` was reclaimed with
      `sweeping staged dir holding no dictionary` (row 8l). Both `docs/TESTING.md` rows are now
      marked ✅.

## 3. Document

- [x] 3.1 Add a `docs/TESTING.md` row for the long-path case (a dictionary whose staged path
      exceeds the old buffer is listed and removable), including the synthetic-fixture recipe,
      since it needs a hand-built tree and would otherwise be missed. **Done** — row 8m, with
      the `run-as` recipe and the unique-name caution.
- [x] 3.2 Note in this change that it supersedes the long-path caveat recorded in the Open
      Questions of `fix-stale-sweep-deletes-live-dictionaries`, so the two are not read as
      contradicting each other once both are archived. **Done** — a "Supersedes the long-path
      caveat" section at the end of `design.md`.
