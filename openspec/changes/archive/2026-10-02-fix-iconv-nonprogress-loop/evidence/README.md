# Evidence: the MDict index-build hang

`diagnostic-instrumentation.patch` is **not** a fix and must never be applied by
the build. It is the temporary instrumentation used to locate the hang, kept so
the measurement can be reproduced.

It was applied to `engine/` during the investigation and then reverted; the
engine tree matches the pinned tag again. It is deliberately stored **here**
rather than in `patches/`, because `scripts/apply-patches.ps1` globs
`patches/*.patch` and would otherwise apply diagnostic logging to every build.

## What it instruments

- `engine/src/dict/mdictparser.cc` — entry/exit of `open()`, `readHeader`,
  `readHeadWordBlockInfos`, `readRecordBlockInfos`; the record-block count
  before it is trusted; the headword-block walk; `readNextHeadWordIndex`.
- `engine/src/dict/mdx.cc` — the index-build sequence from `parser.open()`
  through the headword loop.
- `engine/src/common/iconv.cc` — every iteration of the `Iconv::convert()`
  retry loop, with `result`, `errno`, `inBytesLeft` and `outBufLeft`.

Each line is prefixed `DIAG:`. The guards it adds (a record-block count sanity
check, an iteration cap) exist so a hang prints the offending number instead of
spinning for 90 seconds.

## The measurement it produced

```
DIAG: iconv iter=517000 result=-1 errno=7 inBytesLeft=1 outBufLeft=0
```

517,000 consecutive iterations, byte-identical: `errno=7` is `E2BIG`,
`inBytesLeft` never falls below 1, `outBufLeft` is always 0. The loop grows its
buffer and retries while `iconv` consumes nothing — it cannot terminate on
Android's charset backend, though it terminates under glibc on Windows.

Trace position: the last line before the stall is
`DIAG: rNHWI decompressed -> 32744`; the next statement is
`splitHeadWordBlock`, whose first `toUtf16()` call never returns.

## How to re-run it

```powershell
git -C engine apply ..\openspec\changes\fix-iconv-nonprogress-loop\evidence\diagnostic-instrumentation.patch
# build, import the MDict fixture, then:
adb logcat -v time | Select-String "DIAG: "
# afterwards, restore the engine:
git -C engine checkout -- src/common/iconv.cc src/dict/mdictparser.cc src/dict/mdx.cc
```

## What it ruled out

- a bogus record-block count spinning the build — `numRecordBlocks=29`, correct
- a headword block lacking a NUL terminator — the block walks cleanly and
  terminates at offset 1110 of 32,744
- `MdictParser::open()` as the stall — it completes in about 1 ms
