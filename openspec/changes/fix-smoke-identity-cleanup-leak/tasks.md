## 1. Baseline (the failure this change fixes)

- [x] 1.1 Record the CI evidence: run `37071671665` reports
  `DICT_IDENTITY_SAME=FAIL (name=smoke, copies=2, scan+0)` and
  `DICT_IDENTITY_DIFF=FAIL`, with `MDX_HEADWORD_blood_EXIT=1` as the first hard
  failure. Note that the combined run (`cfg`) and the first MDX run (`cfg-mdx`)
  both pass, so the fault is specific to the *second* invocation on one folder.
- [x] 1.2 Reproduce locally against a clean MDX fixture folder and capture the
  two-invocation sequence: run 1 exits 0 and leaves `dupcheck/smoke.mdx` at
  866 bytes (845 + the 21-byte drift string); run 2 exits 1 with the CI line
  verbatim. Confirm that deleting `dupcheck/` by hand restores run 2 to
  `SAME=OK` / `DIFF=OK`, which establishes the leftover as the sole cause.
- [x] 1.3 Confirm the leak is format-independent: the same run against the DSL
  fixture leaves `dupcheck/aurelex-lingvo.dsl` at 385 bytes (364 + 21), and the
  combined folder never notices only because it is scanned once.

## 2. Smoke tool (`carve/smoke/main.cpp`)

> **Rewritten during implementation.** The original 2.1–2.4 specified a stale-`dupcheck/`
> guard plus a deferred restore *after* `gd_cleanup()`. Measurement falsified the
> second half: the copy cannot be deleted at any point in the tool's lifetime,
> because `MdictParser::open` leaks the `QFile` holding it for the whole process. The
> restore was therefore replaced by D1 (relocate the copy out of the scanned folder)
> and the guard by D2/D3 (assert the shared folder's dictionary set is unchanged).
> See `design.md` D1 and D3.

- [x] 2.1 Move the duplicate copy under `configDir` instead of `dictDir`
  (design.md D1), and rescan `configDir` for it — the original is already loaded
  from the tool's opening `dictDir` scan. Add a comment recording *why* the old
  location was impossible (the leaked `QFile`, with the engine file:line) so the
  next reader does not "tidy" it back.
- [x] 2.2 Assert the shared fixture folder was left untouched: after the identity
  block, check for `dupcheck/` under `dictDir` and print
  `DICT_IDENTITY_CLEANUP=OK`, or `FAIL` naming the offending path and its entries
  (design.md D2). Scope it to the *dictionary set* (no added paths) — the
  re-import block legitimately appends a headword to the original DSL in place, so
  byte-identity would fail on every run.
- [x] 2.3 Keep `QFile::remove( copy )` as best-effort tidying of the config dir,
  with a comment saying the failure is expected and why (the leaked handle), so a
  future reader does not read the leftover as an unfixed bug.
- [x] 2.4 Fold `identityCleanupOk` into the tool's final return expression
  alongside the existing `identityOk`, keeping the existing ordering style.

## 3. Workflow (`.github/workflows/engine-smoke.yml`)

- [x] 3.1 Assert `DICT_IDENTITY_CLEANUP=OK` for the MDX-only run, next to the
  existing `DICT_IDENTITY_SAME` / `DICT_IDENTITY_DIFF` gates (design.md D4), with
  a comment naming what it catches.
- [x] 3.2 Assert the same line for the combined run. That folder is scanned once,
  so this gate is what would have caught the DSL leak at the point it was
  introduced rather than leaving it invisible.
- [x] 3.3 Check the `SKIP`-loop list in the MDX run: `DICT_IDENTITY_CLEANUP` must
  **not** be added to it, since the assertion is checked in every folder, and a
  folder with no self-contained fixture still leaves its dictionary set unchanged.

## 4. Local verification

- [x] 4.1 Rebuild `build-smoke` and re-run the MDX folder with **all three** CI
  invocations (`cfg-mdx`, `cfg-mdx-blood`, `cfg-mdx-cafe`, one config dir each).
  Result: all three exit 0 with `gd_scan_dicts -> 1`, `SAME=OK`,
  `DIFF=OK`, `CLEANUP=OK`; the fixture folder ends holding only `smoke.mdx` at
  845 bytes, unchanged from generation — no `dupcheck/`.
- [x] 4.2 Repeat twice for the DSL fixture, the format whose handle owner is still
  unidentified (design.md Open Questions). Result: `SAME=OK`, `DIFF=OK`,
  `CLEANUP=OK` on both runs and no `dupcheck/` residue. (The non-identity FAILs in
  a DSL-only folder — `GROUP_ALL`, `RESOURCE_*`, `REMOVE_*` — are pre-existing and
  expected: those blocks need the StarDict fixture and are not gated in that shape.)
- [x] 4.3 Verify the new gate is not vacuous: plant `mdx/dupcheck/smoke.mdx` by
  hand. Result: exit 1 with
  `DICT_IDENTITY_CLEANUP=FAIL (the fixture folder was modified: .../mdx/dupcheck/smoke.mdx)`
  while `SAME=OK` / `DIFF=OK` — i.e. the pollution is reported as pollution and the
  block's numbers describe only what it created (design.md D3).
- [x] 4.4 Confirm the combined-folder run is unregressed, since the identity block's
  scan target changed to `configDir`. Result: exit 0, `gd_scan_dicts -> 3`,
  `gd_scan_dicts(again) -> 0 new`, zero `=SKIP` and zero `=FAIL` lines, and every
  pre-existing gate green (`INDEX_PLACEMENT`, `GROUP_*`, `FTS_*`, `OPT_*`,
  `REIMPORT_*`, `REMOVE_*`, `RESOURCE_*`, `STARDICT_LINK_*`,
  `DICT_IDENTITY_CLEANUP=OK`). The undeletable copy is confirmed contained in the
  config dir at `cfg/dupcheck/aurelex-lingvo.dsl` (385 bytes), with the shared
  fixture folder free of residue.

## 5. Documentation

- [x] 5.1 `docs/TESTING.md`: correct the identity-check entry, which recorded only a
  single green local run against each fixture folder. State the property CI actually
  depends on — the tool is hermetic across repeated invocations on one folder — and
  record that it was **false** until this change (the `dupcheck/` copy survived into
  the next invocation's scan).
- [x] 5.2 Note in the same place that the smoke tool must be run **twice against one
  folder**, with different config dirs, to validate a fixture-affecting change, so the
  next harness leak is caught locally rather than by a 27-minute red build. Cross-
  referenced from the "Duplicate dictionaries" section so it is findable from either
  direction.