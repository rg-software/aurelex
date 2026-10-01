## Why

Building a dictionary index on Android can hang **forever** on an MDict file,
with the parser thread spinning in userspace and never finishing. The same file
indexes in under a second on the Windows host. The app is eventually killed with
no crash record, and the user sees an import that never completes.

Measured on device with a real dictionary: `Iconv::convert()` retried **517,000
times** with byte-identical state — `result=-1 errno=7 (E2BIG) inBytesLeft=1
outBufLeft=0` — growing its output buffer on every pass and never consuming
input. The loop cannot terminate on Android's charset backend, though it happens
to terminate under glibc on Windows.

## What Changes

- **`Iconv::convert()` must make progress or stop.** The retry path currently
  treats `E2BIG`/`outBufLeft == 0` as "grow and try again" with no guarantee that
  the retry consumes input. A pass that leaves `inBytesLeft` unchanged is a
  non-progress loop and must terminate the conversion rather than repeat.
- **Bound the retry loop.** Even a correctly-diagnosed `E2BIG` cannot be trusted
  to converge; the loop SHALL carry a hard bound so no charset backend can spin
  it indefinitely.
- **A failed conversion is reported, not fatal to the whole scan.** A word that
  cannot be converted is a data problem in one dictionary; it must not hang or
  abort index builds for every other dictionary in the same import.
- This is an **engine** change and therefore travels through `patches/` as a
  deviation patch, per the repository's merge contract — not a direct edit to
  `engine/`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: the "Index build and validation on device" requirement
  gains the guarantee that an index build **finishes** — it either completes or
  fails with the failure surfaced — rather than running without bound. The
  existing requirement says the system shall build an index and show progress;
  it does not yet say the build must terminate, which is what this change adds.

## Impact

- `engine/src/common/iconv.cc` — `Iconv::convert()` retry loop (via a new
  `patches/` deviation patch).
- `engine/src/dict/mdictparser.cc` — the caller for headwords, if the
  conversion contract changes from "always succeeds" to "can fail".
- `carve/` and the smoke tool, if the conversion failure surfaces through the
  boundary and needs an assertion.
- No QML, app UI, or staging change. No change to which formats are supported.
