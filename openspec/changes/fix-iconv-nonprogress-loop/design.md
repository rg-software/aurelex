## Context

Indexing an MDict file on Android hangs forever. The parser thread spins in
userspace; the process is eventually killed with no crash record. The same file
indexes in under a second on the Windows host.

Measured with temporary instrumentation on device, a real dictionary produced
**517,000 consecutive iterations** of the same call, byte-identical each time:

```
DIAG: iconv iter=517000 result=-1 errno=7 inBytesLeft=1 outBufLeft=0
```

`errno=7` is `E2BIG`; `inBytesLeft` never decreases from 1; `outBufLeft` is
always 0. Each pass takes the "grow the buffer and retry" branch and grows the
allocation, while `iconv` makes no progress. This is a non-progress loop, not a
slow conversion.

## The defect

`engine/src/common/iconv.cc`, `Iconv::convert()`:

```cpp
while ( inBytesLeft > 0 ) {
    result = iconv( state, (char **)&inBuf, &inBytesLeft, (char **)&outBufPtr, &outBufLeft );
    if ( result == (size_t)-1 ) {
        if ( errno == E2BIG || outBufLeft == 0 ) {
            if ( inBytesLeft > 0 ) {
                size_t offset = (char *)outBufPtr - &outBuf.front();
                outBuf.resize( outBuf.size() + dsz );   // grows
                outBufPtr = &outBuf.front() + offset;
                outBufLeft += dsz;                       // "more room"
                continue;                                // retry
            }
        }
        break;
    }
}
```

The retry assumes that having room for more output is enough to make progress.
It is not: on the Android charset backend, `iconv` reports `E2BIG` for this
input and returns without consuming any byte, even after the buffer grows. The
loop then repeats with identical state forever.

The host is unaffected because glibc's `iconv` does not reach this state for the
same input — which is exactly why the defect survived: it is reachable only on
one platform, and MDict on device had never been exercised.

### Why the earlier hypotheses were wrong

Worth recording so they are not re-investigated:

- **"A malformed record-block count spins the build."** Measured false:
  `numRecordBlocks=29`, correct.
- **"A headword block lacking a NUL terminator runs `strlen` off the end."**
  Measured false: the block was decompressed and walked offline; every entry is
  properly terminated and the walk ends at offset 1110 of a 32,744-byte block.
- The parse itself is **correct**: `MdictParser::open()` completes in ~1 ms with
  sane values.

The trace stops where it does because the first `toUtf16()` call inside
`splitHeadWordBlock` never returns — the conversion, not the parse, is the hang.

## Decision: terminate on no progress, and bound the loop

Two independent guards, because either alone can be defeated:

1. **Non-progress detection.** If a retry leaves `inBytesLeft` unchanged, the
   conversion cannot succeed by retrying. Stop and report failure. This is the
   direct fix for the measured defect and does not depend on knowing which
   charset backend misbehaves.
2. **A hard iteration bound.** Even a legitimately-growing conversion must not
   be able to loop indefinitely. The bound converts any future variant of this
   bug from "hangs forever" into "fails visibly".

The bound is deliberately generous — it is a backstop against runaway loops, not
a performance tuning knob. Real conversions complete in a handful of passes.

## Decision: a failed conversion fails the word, not the scan

A word whose text cannot be converted is a property of one dictionary's data.
The index build for that dictionary should report failure; the other
dictionaries in the same import must still index and become searchable. This is
already the contract for a dictionary that fails to load, and a failed index
build should behave the same way rather than propagating an exception that
aborts the whole scan.

## Decision: ship as a deviation patch

This is engine code. Per `AGENTS.md` rule 1 the engine tree is never edited in
place; the fix lands as a new `patches/` entry so a release bump keeps
`git diff` across the pinned tag small and reviewable. The patch must be
self-contained and carry its own justification comment.

## Risks / Trade-offs

- **[Terminating loses articles]** If a conversion genuinely needs more passes
  than the bound allows, words would fail that previously succeeded. → Mitigated
  by the bound being far above observed behaviour, and by failure being
  per-word and reported rather than silent.
- **[The host does not reproduce the defect]** A fix cannot be validated on
  Windows. → Verification is on device, with the same instrumentation used to
  find it; the non-progress guard is also unit-testable in isolation because it
  depends only on `inBytesLeft` not advancing.
- **[Charset backend specifics]** The exact bionic behaviour is not fully
  characterised. → The fix deliberately does not encode an assumption about
  *which* errno or backend is at fault; it stops when progress stops.

## Verification plan

1. Host: the existing smoke assertions still pass (they pass today, so they are
   a regression guard, not a proof of the fix).
2. Device: import the dictionary that reproduced the hang; the index build
   completes and the dictionary becomes searchable with its headwords intact.
3. Device: confirm the failing path is exercised — with the guard made
   artificially strict, the build fails and reports rather than hanging.
