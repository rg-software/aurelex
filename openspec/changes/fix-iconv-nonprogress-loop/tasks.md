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

- [ ] 2.1 Add non-progress detection to `Iconv::convert()`: a pass that leaves
  `inBytesLeft` unchanged terminates the conversion instead of retrying
- [ ] 2.2 Add a hard iteration bound as a backstop, so no future variant can
  loop without bound
- [ ] 2.3 Report the failure rather than returning a silently truncated string —
  the caller must be able to distinguish "converted" from "could not convert"
- [ ] 2.4 Review the other `Iconv` entry points (`toQString`, `toWstring`,
  `fromUnicode`) for the same non-progress assumption

## 3. Contain the failure

- [ ] 3.1 A word that cannot be converted fails that dictionary's index build
  with the failure reported; it does not hang, and it does not abort the other
  dictionaries in the same scan
- [ ] 3.2 Confirm the failure surfaces to the user rather than only to the log,
  consistent with how a dictionary that fails to load is already reported

## 4. Ship through the patch pipeline

- [ ] 4.1 Add the fix as a new `patches/` deviation patch with its own
  justification comment; do not edit `engine/` in place
- [ ] 4.2 Delete `patches/9999-diagnostic-mdx-hang.patch` and its README once the
  fix is in — the instrumentation was a diagnostic, not a deliverable
- [ ] 4.3 Confirm the patch applies cleanly to a pristine submodule via
  `scripts/apply-patches.ps1`, and that a release bump would keep the diff small

## 5. Verify

- [ ] 5.1 Host: all existing smoke assertions still pass
- [ ] 5.2 Device: import the dictionary that hung; the index build completes and
  the dictionary is searchable with its headwords intact
- [ ] 5.3 Device: confirm the failure path is real — with the bound made
  temporarily strict, the build fails and reports instead of hanging
- [ ] 5.4 Confirm no other dictionary in the same import is affected

## 6. Documentation

- [ ] 6.1 `docs/TESTING.md`: record the MDict index-build hang and its fix, so
  the symptom ("import never completes, no crash") is searchable
- [ ] 6.2 Record the ruled-out hypotheses (record-block count, missing
  terminator) in `design.md` so they are not re-investigated
- [ ] 6.3 Note that MDict index building is now covered on device, which it was
  not before this change

## Notes

The defect was found while verifying MDict import (`verify-mdx-import`). It is
**not** part of that change: the hang is in the engine's charset wrapper, is
reachable by any MDict file, and is unrelated to staging or the loose-resource
rule. `verify-mdx-import`'s own claim is verified on host; its device pass was
blocked by this defect, which is recorded in that change rather than here.
