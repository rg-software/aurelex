## Context

`carve/smoke/main.cpp` is a single executable that asserts everything about the
engine in one walk: StarDict resources, DSL hidden zones, StarDict
cross-references, FTS, re-import and removal. It was written when there was one
fixture layout — the combined folder CI builds.

`3dace1c` added a **second** invocation against an MDX-only folder. Three of the
tool's blocks need fixtures that folder does not contain, and one of them calls
`return 1` outright, so the new run cannot pass. Meanwhile the workflow's
`set -e` swallows the exit code before it can be printed, so the failure is
silent.

## Decision: scope each block to its fixture, and make skips explicit

**The tool reports what it found, and skips what it cannot test.** Each
format-specific block determines whether its fixture is present, and prints
`=SKIP` instead of `=FAIL` when it is not. A `SKIP` does not count towards the
exit code. The format-agnostic gates — scan, `INDEX_PLACEMENT`, dedup on
re-scan, a non-empty lookup, and the article markers — stay unconditional, so
the MDX run still gates exactly what it was added to gate. Without that, "make
it not fail" would quietly reduce the MDX run to a smoke test of nothing.

**The inventory is printed.** A line naming the fixtures detected in the scanned
folder (`FIXTURES: mdx`, `FIXTURES: stardict dsl`) turns "why did this block
skip" into something readable from the log, rather than something to infer from
which assertion is missing.

**The hard abort goes.** `return 1` when no `.ifo` is present was correct for a
tool that assumed StarDict was always there. With scoping it is simply the
StarDict blocks being skipped, and the walk continues to the blocks whose
fixtures *are* present. That also fixes the secondary effect: everything after
line 428 — resource-thread, re-import, removal — ran only in the combined
folder, and now runs wherever its fixtures exist.

**Recommendation — the FTS block is a one-off.** It is the one block that is
neither format-agnostic nor cleanly scoped: it indexes the StarDict fixture
specifically. It is scoped on the `.ifo` fixture's presence like the others. Noted
here because "is this block still meaningful in the MDX folder" is the question
to ask of every block, and this is the one where the answer is "no, and that is
fine".

## Decision: skips must be asserted, not tolerated

A `=SKIP` that is merely allowed is a hole: a folder missing *everything* would
skip every block and exit 0. That is the same vacuous-coverage failure as an
assertion with no input, which this work has already hit twice.

So each invocation asserts its **expected** skips:

- the MDX-only run expects the StarDict and DSL blocks to be `=SKIP`
- the combined run expects **no** skips

A fixture that silently stops being generated therefore fails the build in the
invocation that expected it, rather than passing everywhere.

## Decision: capture exit codes explicitly

`mdxout=$(cmd)` under `set -e` aborts the step before `mdxex=$?` runs, discarding
both the exit code and the output. Every such call site becomes:

```bash
if mdxout=$(cmd 2>&1); then mdxex=0; else mdxex=$?; fi
```

which cannot be short-circuited. This is the change that makes the *next* such
failure legible, and it is worth doing even where the exit code was already
being checked.

## Decision: a local MDX-only run

The tool was green locally and red in CI because a local run used the combined
folder — the one layout it was written for. `docs/DEVELOPMENT.md` gains the
invocation for each layout, so the difference is visible and a change can be
checked against the layout CI actually uses.

## Risks / Trade-offs

- **[Scoping weakens the gate]** Making blocks skippable could let a real
  regression pass because its block *thinks* it has no fixture. → Skips are
  asserted per invocation, and the format-agnostic gates are never skippable.
- **[Fixture detection is heuristic]** A block decides its own fixture's
  presence from the scanned set. → Detection is by the same suffix lookup the
  blocks already use, and the printed inventory makes a wrong call visible.
- **[Two layouts, more call sites]** Every additional layout multiplies the
  invocations and their expected skips. → Bounded to two today; the pattern is
  stated so a third is deliberate rather than accidental.

## Verification

- Both invocations pass: the MDX-only folder and the combined folder.
- The MDX run reports its expected skips **and** its format-agnostic gates as
  `=OK`, so the scan, index placement and article markers are still enforced
  there.
- Removing a fixture from a folder fails the invocation that expects it, rather
  than silently skipping.
- The workflow's failure path prints the tool's output — induced by making an
  assertion fail deliberately and confirming the message reaches the log.
