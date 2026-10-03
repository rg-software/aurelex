## Why

The engine smoke workflow is red on every push carrying `af4b713` (`feat(dicts):
resolve duplicate dictionaries by name and content`), and the red is a **harness
fault reported as a product failure**. Identity resolution itself is fine.

`af4b713` added the `DICT_IDENTITY_*` block to `carve/smoke/main.cpp`, and with
it a `dupcheck/` copy it makes inside the scanned fixture folder. The block ends
by tidying that copy away:

```cpp
// Leave the fixture folder as it was found.
QFile::remove( copy );   // return value discarded
```

**That removal never succeeds on the CI runner.** The copy is still *loaded* at
that point, and Windows denies delete on a file with an open handle. For MDX this
is explicit in the engine: `MdxDictionary` opens `dictFile` in its constructor
(`engine/src/dict/mdx.cc:308-311`) and closes it only in its destructor
(`mdx.cc:320-327`), which runs at `gd_cleanup()` — strictly *after* the removal.
So the drifted copy is silently left behind in the fixture folder.

`.github/workflows/engine-smoke.yml` then runs the tool **three times against the
same `$RUNNER_TEMP/mdx` folder** (`cfg-mdx`, `cfg-mdx-blood`, `cfg-mdx-cafe`).
The first invocation passes and leaks; the second inherits the leak and fails:

| invocation | scan | `DICT_IDENTITY_SAME` | exit |
| --- | --- | --- | --- |
| `cfg-mdx` (word `smoke`) | `-> 1` | `OK (name=smoke, copies=2, scan+1)` | 0 |
| `cfg-mdx-blood` (word `blood`) | `-> 2` | `FAIL (name=smoke, copies=2, scan+0)` | 1 |

Run 2 fails for two compounding reasons, both artefacts of the leftover:

- the scan now finds **two** dictionaries named `smoke`, so `ids.size() >= 2`
  holds but `sameContent()` is false — the original against the *drifted* copy;
- `QFile::copy` cannot overwrite the leftover, so `copied == false`, which makes
  `scan+0` and leaves `differs` at its initial `false` — hence
  `DICT_IDENTITY_DIFF=FAIL`.

**Reproduced locally, twice, byte for byte** (`build-smoke/Release`, git-bash):

```
run 1: gd_scan_dicts -> 1  DICT_IDENTITY_SAME=OK (copies=2, scan+1)  DICT_IDENTITY_DIFF=OK  exit 0
       folder now holds:  dupcheck/smoke.mdx   866 bytes          <- leaked
run 2: gd_scan_dicts -> 2  DICT_IDENTITY_SAME=FAIL (copies=2, scan+0)  DICT_IDENTITY_DIFF=FAIL  exit 1
```

`866 = 845 + len("\nidentitydrift\n\tmore\n")` — the leak is exactly the drifted
copy. Deleting `dupcheck/` by hand and re-running restores `SAME=OK` / `DIFF=OK`,
which confirms the leftover is the sole cause. This is deterministic, not a flake.

### The leak is format-independent, and that is the wider problem

It is not an MDX quirk. The same run against the **DSL** fixture leaks
identically (`dupcheck/aurelex-lingvo.dsl`, 385 vs 364 bytes). It never surfaced
only because `$RUNNER_TEMP/dic` is scanned exactly once, so nothing ever re-reads
its polluted folder.

Two things follow, and they are the reason this is worth a change rather than a
one-line `QFile::remove` fix:

1. **`docs/TESTING.md` / `tasks.md` 5.9 overstate what was verified.** That task
   records the tool as run locally against both fixture folders with
   `DICT_IDENTITY_SAME=OK` / `DICT_IDENTITY_DIFF=OK`, exit 0. That was true — of
   *single* invocations on clean folders. The property CI depends on is that the
   tool is **hermetic**, i.e. safe to run repeatedly against one folder, and that
   was never the thing checked. Same shape as the immediately preceding
   `fix-smoke-fixture-scoping`, where the wiring was green in the environment it
   was authored in and red in the one that mattered.
2. **A silently-ignored cleanup is exactly the failure mode this workflow has now
   hit twice.** `fix-smoke-fixture-scoping` fixed the first instance (an exit code
   swallowed by `set -e`, leaving "a bare exit 1 with no `SMOKE FAILED` line").
   Here the return value is discarded, and the next process inherits the mess. The
   general lesson is that a smoke check which mutates shared state must either
   restore it verifiably or assert that it did.

## What Changes

- **The duplicate copy moves out of the shared fixture folder entirely.** It is
  created under the *per-invocation* config dir instead, which nothing ever scans
  twice. This is the key finding: the copy **cannot be deleted** at any point in
  the tool's lifetime, because `MdictParser::open` leaks the `QFile` holding it for
  the whole process — so "restore the folder afterwards" is not an available design
  (measured: the delete fails immediately, after `gd_remove_dict()`, and after
  `gd_cleanup()`). Removing the *need* for the delete makes hermeticity structural
  instead of dependent on a cleanup that provably cannot run.
- **The shared folder is asserted untouched, not assumed.** A new
  `DICT_IDENTITY_CLEANUP=OK|FAIL` line is printed and folded into the tool's exit
  code, naming any offending path. It is checked on every run, so it is also the
  proof that the copy really did stay out of the fixture folder.
- **A polluted fixture folder is reported as pollution, not as identity drift.**
  Because the copy no longer lands there, the block's own numbers (`copies=`,
  `scan+`, `SAME`, `DIFF`) always describe the state the block itself created, and
  a leftover from any cause is caught by the assertion above with its path named.
  This is the difference between a harness bug and a product bug being visible in
  the log.
- **The workflow gates the new line** for both the MDX-only and the combined run,
  matching the existing per-line assertion style.
- **`docs/TESTING.md` records what was actually verified** — hermetic across
  repeated invocations on one folder — rather than a single green run.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is build-time tooling and CI wiring, not user-visible behaviour, so no
spec requirement changes. `.openspec.yaml` sets `skip_specs: true`.

## Impact

- `carve/smoke/main.cpp` — relocate the identity block's duplicate copy from the
  scanned fixture folder to the config dir, and add the asserted
  `DICT_IDENTITY_CLEANUP` check that the fixture folder's dictionary set is
  unchanged.
- `.github/workflows/engine-smoke.yml` — assert `DICT_IDENTITY_CLEANUP=OK` in both
  the MDX-only and combined runs.
- `docs/TESTING.md` — correct the recorded verification for `af4b713`'s identity
  check to state the hermetic property, and note the leak that made it false.
- No engine, patch, boundary, or app change.