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
- [ ] 1.5 Establish whether `set -e` is the *only* swallow at those call sites,
  or whether the `for w in blood cafe` loop fails for a second reason too

## 2. Scope the smoke tool's blocks

- [ ] 2.1 Detect the fixtures present in the scanned folder and print an
  inventory line (`FIXTURES: mdx` / `FIXTURES: stardict dsl`), so a skip is
  readable from the log rather than inferred
- [ ] 2.2 Make each format-specific block print `=SKIP` when its fixture is
  absent, and stop counting a skip as a failure
- [ ] 2.3 Remove the hard `return 1` for a missing StarDict fixture, so the walk
  continues to whichever blocks do have their fixtures
- [ ] 2.4 Keep the format-agnostic gates unconditional: scan, `INDEX_PLACEMENT`,
  dedup on re-scan, a non-empty lookup, the article markers. The MDX run must
  still gate what it was added to gate
- [ ] 2.5 Decide each block's disposition explicitly — format-agnostic, scoped,
  or meaningless outside the combined folder (the FTS block indexes the StarDict
  fixture specifically). Record the disposition so a future fixture does not get
  guessed at

## 3. Make the workflow able to report

- [ ] 3.1 Capture exit codes so `set -e` cannot short-circuit:
  `if out=$(cmd 2>&1); then ex=0; else ex=$?; fi`, at **every** such call site
  including the `for w in blood cafe` loop
- [ ] 3.2 Print the captured output on the failure path, so a red run names the
  assertion that failed instead of a bare exit code
- [ ] 3.3 Induce a deliberate assertion failure and confirm the message reaches
  the CI log — verifying the reporting path rather than assuming it

## 4. Stop skips from rotting into vacuous passes

- [ ] 4.1 The MDX-only run asserts its **expected** skips (StarDict and DSL
  blocks) as well as its `=OK` gates
- [ ] 4.2 The combined run asserts **no** skips
- [ ] 4.3 Confirm a folder missing a fixture fails the invocation that expects
  it, rather than skipping everywhere and passing. A SKIP that is merely
  tolerated is a hole: a fixture that silently stops being generated would pass
  in every invocation

## 5. Make the local/CI difference visible

- [ ] 5.1 `docs/DEVELOPMENT.md`: document the invocation for each fixture layout,
  since a local run currently uses the combined folder while CI also runs the
  MDX-only one — which is how the tool was green locally and red in CI
- [ ] 5.2 Run both invocations locally as part of the documented procedure, so a
  change is checked against the layout CI uses

## 6. Verify end to end

- [ ] 6.1 The MDX-only run passes: expected skips and `=OK` gates
- [ ] 6.2 The combined run passes with no skips
- [ ] 6.3 The existing 16-plus assertions still pass unchanged in the combined
  folder — no block was weakened to make the MDX run green
- [ ] 6.4 Push and confirm the workflow is green, which is the only proof that
  matters and the step that was skipped last time

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
