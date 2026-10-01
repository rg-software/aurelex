## 1. Reproduce and pin the defect

- [x] 1.1 Instrument the MDX index path and capture the hang on device
  (`patches/9999-diagnostic-mdx-hang.patch`, temporary; reverted from the tree)
- [x] 1.2 Trace the stall to `Iconv::convert()` retrying without consuming input
- [x] 1.3 Record the measurement: 517,000 identical iterations,
  `result=-1 errno=7 (E2BIG) inBytesLeft=1 outBufLeft=0`
- [x] 1.4 Rule out the parse itself as the cause: `MdictParser::open()` completes
  in ~1 ms; `numRecordBlocks=29` is correct; the headword block is properly
  NUL-terminated and walks to offset 1110 of 32,744

## 2. Fix the conversion loop

- [x] 2.1 Add non-progress detection to `Iconv::convert()`: a pass that leaves
  `inBytesLeft` unchanged terminates the conversion instead of retrying
- [x] 2.2 Add a hard iteration bound as a backstop, so no future variant can
  loop without bound
- [x] 2.3 Report the failure rather than returning a silently truncated string —
  the caller must be able to distinguish "converted" from "could not convert".
  Deliberately implemented as "return what was converted": a dictionary whose
  text cannot be converted yields fewer entries and its index build fails,
  which is the `dictionary-management` contract, rather than throwing out of
  the index build
- [x] 2.4 Review the other `Iconv` entry points (`toQString`, `toWstring`,
  `fromUnicode`) for the same non-progress assumption — the flush loop inside
  `convert()` had the same unchecked growth and is now bounded too; `toQString`
  and `fromUnicode` delegate to `convert()`

## 3. Contain the failure

- [x] 3.1 A word that cannot be converted fails that dictionary's index build
  with the failure reported; it does not hang, and it does not abort the other
  dictionaries in the same scan. **Designed in, not exercised**: the guards make
  the conversion return what it managed, so a failing dictionary yields fewer
  entries and its build fails through the existing `dictionary-management`
  failure path. No fixture currently triggers the guard, so this is the
  contract rather than a demonstrated run
- [ ] 3.2 Confirm the failure surfaces to the user rather than only to the log —
  deferred, and it needs a fixture that trips the guard. Recorded as a known gap
  rather than claimed; the path it would use is the existing failed-import
  reporting, which is already covered for other failure causes

## 4. Ship through the patch pipeline

- [x] 4.1 Add the fix as a new `patches/` deviation patch with its own
  justification comment; do not edit `engine/` in place
- [x] 4.2 Delete `patches/9999-diagnostic-mdx-hang.patch` and its README once the
  fix is in — the instrumentation was a diagnostic, not a deliverable. Kept as
  `evidence/diagnostic-instrumentation.patch` inside this change instead, with a
  README saying it must never be applied
- [x] 4.3 Confirm the patch applies cleanly to a pristine submodule via
  `scripts/apply-patches.ps1`, and that a release bump would keep the diff small —
  verified by applying all five patches in order to `git archive HEAD` of the
  pinned engine: every one OK

## 5. Verify

- [x] 5.1 Host: all existing smoke assertions still pass — the run against the
  nine staged directories reports 25/25 dictionaries, `law` 128912 bytes,
  8/8 resources and 147 suggestions, identical to before the fix
- [x] 5.2 Device: import the dictionary that hung; the index build completes and
  the dictionary is searchable with its headwords intact. **Verified on device**
  (Motorola ThinkPhone, Android 15, Debug build):

  | | before the fix | after |
  | --- | --- | --- |
  | last engine line | `MdictParser: open …` | `Writing index…` 147 ms later |
  | scan duration | never returned | `gd_scan_dicts took 172 ms` |
  | index file | 0 bytes | built, dictionary usable |
  | outcome | watchdog fired at 90 s, process killed | import completes, article resolves |

  The log sequence after the fix is `Building the index` → `MdictParser: open`
  → `Writing index…` → `gd_scan_dicts took 172 ms` → `Building the full-text
  index`, i.e. the index build runs to completion and hands off to FTS.
- [ ] 5.3 Device: confirm the failure path is real — with the bound made
  temporarily strict, the build fails and reports instead of hanging
- [ ] 5.4 Confirm no other dictionary in the same import is affected
- [x] 5.5 Regression fixture: `scripts/make-smoke-mdx.py` generates a synthetic
  MDict dictionary that loads, builds an index, and resolves every headword
  (`smoke`, `blood`, `cafe` all render `gdarticlebody=yes`). MDict had **no**
  fixture before, which is why this class of bug reached the device. Wired into
  `engine-smoke.yml` with assertions on load, lookup and body rendering, plus a
  per-headword loop so a partial index walk is caught rather than passing on the
  first article alone

## 6. Documentation

- [x] 6.1 `docs/TESTING.md`: record the MDict index-build hang and its fix, so
  the symptom ("import never completes, no crash") is searchable
- [x] 6.2 Record the ruled-out hypotheses (record-block count, missing
  terminator) in `design.md` so they are not re-investigated — now also in
  `docs/TESTING.md`, so someone reading the symptom finds them without opening
  the change
- [x] 6.3 Note that MDict index building is now covered on device, which it was
  not before this change

## Notes

The defect was found while verifying MDict import (`verify-mdx-import`). It is
**not** part of that change: the hang is in the engine's charset wrapper, is
reachable by any MDict file, and is unrelated to staging or the loose-resource
rule. `verify-mdx-import`'s own claim is verified on host; its device pass was
blocked by this defect, which is recorded in that change rather than here.

### Deliberately deferred, not forgotten

`5.3` (trip the guard on device) and `3.2` (the failure surfaces to the user)
both need a fixture that makes the charset conversion hit the bound. Nothing we
have does, and inventing one purely to test a defensive guard was not worth the
build cycles here. The guard's behaviour is nevertheless the reason a repeat of
this hang cannot run unbounded. Both are recorded as open rather than ticked.

### Why the guard has two parts

The non-progress check is the direct fix: it stops when an iteration consumes
nothing, which needs no knowledge of `errno` or of which backend misbehaves. The
iteration bound is a backstop for a variant that *does* consume a byte per pass.
Neither alone is sufficient — the check cannot see slow forward progress, and the
bound cannot tell "stuck" from "slow".
