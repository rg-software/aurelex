## 1. Surface engine diagnostics

- [x] 1.1 Construct a `QCoreApplication` in the smoke tool's `main`
- [x] 1.2 Install a `qInstallMessageHandler` callback that prefixes each
  message with its severity
- [x] 1.3 Write diagnostics to **stderr**, so they cannot interleave with the
  stdout lines the CI assertions grep

## 2. Verify

- [x] 2.1 Confirm a fixture the engine rejects now reports the engine's own
  reason (observed: `MDict: parseCompressedBlock: plain: checksum not match`),
  where the tool previously printed nothing
- [x] 2.2 Confirm the existing CI assertions still pass — the smoke run against
  the nine staged directories reports 25/25 dictionaries, `law` 128912 bytes and
  8/8 resources, unchanged
- [x] 2.3 Confirm stdout is unaltered, so the assertions that read it are
  unaffected

## Notes

Found while diagnosing the MDict index-build hang (`fix-iconv-nonprogress-loop`).
Kept as its own change because it is independently valuable and unrelated to
that defect: any future format investigation on the host benefits, and it is the
reason the engine's error text was finally visible.

The MDict fixture generator spawned by that investigation lives in
`fix-iconv-nonprogress-loop`, where it serves as that bug's regression fixture.
