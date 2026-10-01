## Why

The engine smoke workflow is red, and it went red silently. Both since this
repository added an MDX-only run to it.

Two defects combine:

**1. The smoke tool assumes the combined CI folder.** It was written for one
layout — StarDict + `.dsl.dz` + a nested `.dsl` — and hard-fails when those
fixtures are absent. `3dace1c` added a second invocation against an MDX-only
folder, whose headwords are `smoke`/`blood`/`cafe` only:

| Block | Needs | MDX-only folder |
| --- | --- | --- |
| `optPartsOk` — `gd_lookup("sun")`, `gd_lookup("water")` | the DSL fixtures | no such headword → `=FAIL` |
| `stardictLinkOk` — `gd_lookup("clot")` | the StarDict fixture | no such headword → `=FAIL` |
| `findDictBySuffix(".ifo")` | a StarDict primary file | `-1` → **`return 1`, hard abort** |

So the MDX run cannot pass, and everything after the abort — resource-thread,
re-import, removal — never runs.

**2. The workflow hides the reason.** The invocation assigns a command
substitution:

```bash
mdxout=$(./build-gh/Release/aurelex_smoke.exe … 2>&1)
mdxex=$?
```

GitHub runs bash with `-e`, so a non-zero substitution aborts the step **before**
`mdxex=$?` is reached. The tool's output is captured into `$mdxout` and never
printed on that path. The observed failure is therefore `SMOKE_EXE_EXIT=0`, no
`MDX_SMOKE_EXE_EXIT=` line, no `SMOKE FAILED:` message, and a bare exit 1 —
which reads like an infrastructure fault rather than a broken assertion.

Reproduced locally with git-bash: under `set -e` the script emits **nothing** and
exits 1; the identical script without `set -e` reaches the echo and reports
`ex=1`. The `for w in blood cafe` loop has the same latent defect, though its
headwords do exist, so only the swallow affects it.

**Why it sat unnoticed.** The workflow triggers only on `engine/**`, `patches/**`,
`carve/**`, `.github/workflows/**`. The pushes between the last green run and
this discovery touched none of those, so nothing re-ran it. The tool was green
locally because a local run uses the combined fixture set, which is the one
layout the tool was written for.

### This is a verification failure, not only a CI failure

The task that added this wiring was ticked as complete on the strength of a local
run against the *combined* folder, while CI runs the MDX folder. The check was
green in the environment it was authored in and red in the environment that
matters — the same shape as two earlier assertions in this work that passed while
the device failed. The fixture itself is sound; the wiring was never verified.

## What Changes

- **The smoke tool scopes format-specific blocks to the fixtures present.** Each
  block detects whether its fixture is in the scanned folder, prints the detected
  inventory, and reports `=SKIP` rather than `=FAIL` when absent. The hard
  `return 1` for a missing StarDict fixture goes.
- **Format-agnostic gates stay unconditional**, so the MDX run still gates what
  it was added to gate: the scan, `INDEX_PLACEMENT`, dedup on re-scan, a
  non-empty lookup, and the article markers.
- **The workflow captures exit codes explicitly** (`cmd && ex=0 || ex=$?`) at
  every such call site, so `set -e` cannot swallow diagnostics again.
- **The workflow asserts the expected skips per folder.** A skip must be
  *expected*, not merely tolerated: otherwise a folder could skip every block and
  pass vacuously, which is the failure mode this change is fixing.
- **A local way to run the tool against the MDX-only folder exists**, so this
  class of failure is catchable before CI rather than only by pushing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is build-time tooling and CI wiring, not user-visible behaviour, so no
spec requirement changes. `.openspec.yaml` sets `skip_specs: true`.

## Impact

- `carve/smoke/main.cpp` — per-format block scoping, the inventory line, the
  `=SKIP` results, and the removed abort.
- `.github/workflows/engine-smoke.yml` — exit-code capture, skip assertions, and
  a runnable MDX-only invocation.
- `docs/DEVELOPMENT.md` — how to run the smoke tool against each fixture layout
  locally, since a local run silently differs from CI today.
- No engine, patch, boundary, or app change.
