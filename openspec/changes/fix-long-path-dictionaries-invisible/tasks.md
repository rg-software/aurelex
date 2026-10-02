## 1. Widen the app's dictionary-info buffers

- [ ] 1.1 Add one shared constant for the dictionary-info buffer size (`PATH_MAX`) in
      `app/EngineController.cpp`, sized so any path a filesystem can produce fits, with a
      comment recording why the size matters: `gd_dict_info` refuses a path that does not
      fit rather than truncating it, and a truncated path would be *wrong* data that could
      match a different staged directory in the sweep's prefix comparison.
- [ ] 1.2 Use that constant for both buffers in `readDictInfoAt()` (`char name[256]` /
      `char file[512]` today), so the model and the sweep's in-use set are computed from the
      same, complete source paths.
- [ ] 1.3 Use it for the FTS indexing loop's `nb` / `fb` too, and comment there that `fb` is
      unused but cannot be dropped: `gd_dict_info` (`:906`) rejects a null file buffer, so a
      caller that only wants the name must still supply one.
- [ ] 1.4 Add a `static_assert` that the constant is at least `PATH_MAX`, so the buffer
      cannot silently shrink below a legal path again.

## 2. Verify

- [ ] 2.1 Build the app (`app/build.ps1`) and the host test binary; confirm both compile and
      that the host suite still passes, with no behaviour change for paths that already fit
      the old buffers.
- [ ] 2.2 Recreate the long-path fixture on a debug device (the one used to prove the defect):
      two staged trees straddling the old 512-byte boundary, each holding a valid dictionary,
      one under and one over. Confirm the over-boundary dictionary is now **listed**, and that
      the Dicts list count matches `gd_dict_count` on a cold start.
- [ ] 2.3 Remove the long-path dictionary through the Dicts list and confirm its staged copy
      and built index are deleted, that it stops appearing in lookups, and that its directory
      is reclaimed.
- [ ] 2.4 Re-confirm the two behaviours that must not regress, per `docs/TESTING.md` rows 8k
      and 8l: a nested import still survives a restart, and a genuinely empty leftover staged
      directory is still reclaimed.

## 3. Document

- [ ] 3.1 Add a `docs/TESTING.md` row for the long-path case (a dictionary whose staged path
      exceeds the old buffer is listed and removable), including the synthetic-fixture recipe,
      since it needs a hand-built tree and would otherwise be missed.
- [ ] 3.2 Note in this change that it supersedes the long-path caveat recorded in the Open
      Questions of `fix-stale-sweep-deletes-live-dictionaries`, so the two are not read as
      contradicting each other once both are archived.
