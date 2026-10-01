## 1. Reproduce and confirm

- [x] 1.1 Confirm the hard abort: `findDictBySuffix(".ifo") < 0` → `return 1`
  (lines 424-428), so nothing after it runs
- [x] 1.2 Confirm the MDX-only folder lacks `sun` / `water` / `clot`, so the
  `optPartsOk` and `stardictLinkOk` blocks report `=FAIL` there
- [x] 1.3 Reproduce the silent failure with git-bash: under `set -e` the script
  emits **nothing** and exits 1; the identical script without `set -e` reaches
  the echo and reports `ex=1`. This is the mechanism behind
  `SMOKE_EXE_EXIT=0` with no `MDX_SMOKE_EXE_EXIT=` and no `SMOKE FAILED:`
- [x] 1.4 Note why it went unnoticed: the workflow triggers only on
  `engine/**`, `patches/**`, `carve/**`, `.github/workflows/**`, and the pushes
  since the last green run touched none of those
- [x] 1.5 Establish whether `set -e` is the *only* swallow at those call sites.
  **It is the same hazard at both**: the combined run at line 153 had it too,
  identically latent. The `for w in blood cafe` loop's headwords do exist, so its
  only problem was the swallow

## 2. Scope the smoke tool's blocks

- [x] 2.1 Detect the fixtures present and print an inventory line — a
  `FixturePresence` derived from the **loaded dictionaries** rather than the
  filesystem, so detection and use cannot disagree
- [x] 2.2 Format-specific blocks print `=SKIP (no <fixture> fixture)` when their
  fixture is absent, and a skip no longer fails the run
- [x] 2.3 The hard `return 1` is gone; the walk now continues into the blocks
  whose fixtures **are** present, which is why re-import, removal and the
  resource-thread blocks finally run in the MDX folder
- [x] 2.4 Format-agnostic gates stay unconditional: scan, `INDEX_PLACEMENT`,
  dedup on re-scan, a non-empty lookup, the article markers
- [x] 2.5 Each block's disposition recorded in the source: the **FTS** block
  indexes the StarDict fixture specifically, so it is scoped to it and skips in
  an MDX folder — the one block where "meaningful here" is genuinely no

## 3. Make the workflow able to report

- [x] 3.1 Exit codes captured so `set -e` cannot short-circuit, at **every**
  call site including the combined run and the per-headword loop
- [x] 3.2 Captured output printed on the failure path
- [x] 3.3 Induced a deliberate assertion failure and confirmed the message
  reaches the log. **Verified**: before the fix the same scenario printed
  *nothing* and exited 1; after it prints `SMOKE_EXE_EXIT=1`, the tool's output
  including the failing assertion, and `SMOKE FAILED: exe exited 1`

## 4. Stop skips from rotting into vacuous passes

- [x] 4.1 The MDX-only run asserts its **expected** skips — all twelve — as well
  as its `=OK` gates
- [x] 4.2 The combined run asserts **no** skips: a skip there means a fixture
  stopped being generated
- [x] 4.3 A folder missing a fixture now fails the invocation that expects it.
  Both directions verified: MDX-only reports 12 skips and passes; combined
  reports 0 skips and passes; each asserts the other's state would be a failure

## 5. Make the local/CI difference visible

- [x] 5.1 `docs/DEVELOPMENT.md` documents running the tool against **both**
  layouts, with the commands, plus two rules the incident produced: a `=SKIP` is
  not a pass, and never capture an exit code as `out=$(cmd)` under `set -e`
- [x] 5.2 Both invocations run locally as part of the documented procedure

## 6. Verify end to end

- [x] 6.1 The MDX-only run passes: **EXIT=0, zero FAILs**, 12 expected skips,
  `FIXTURES: mdx`
- [x] 6.2 The combined run passes with **no skips**: EXIT=0, zero FAILs,
  `FIXTURES: stardict dsl`
- [x] 6.3 All existing assertions still pass unchanged in the combined folder —
  15 `_OK` results including the StarDict link, FTS, resource-thread, re-import
  and removal blocks. No block was weakened to make the MDX run green
- [ ] 6.4 Push and confirm the workflow is green — the only proof that matters,
  and the step that was skipped last time

## Notes

Found by CI going red after `3dace1c`, which added the MDX-only invocation. That
commit is `fix-iconv-nonprogress-loop`, whose task 5.5 claimed the wiring was
done — ticked on a local run against the **combined** folder while CI runs the
MDX folder. The fixture is sound; the wiring was never verified. 5.5 is corrected
to point here.

This is the third assertion in that body of work to pass in the environment it
was authored in and fail in the one that matters, after two in
`stardict-bword-link-navigation` that checked a substring of a URL rather than
the URL the app parses. The common cause is checking something adjacent to the
contract; the common remedy is asserting the exact thing the consumer does, in
the environment the consumer runs in.
