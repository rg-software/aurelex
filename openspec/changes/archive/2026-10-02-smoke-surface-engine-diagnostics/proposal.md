## Why

The host smoke tool silently discards every `qWarning`/`qDebug` the engine
emits. The tool has no `QCoreApplication`, and without an application object
Qt has nowhere to deliver messages on this platform, so they are dropped.

That matters because the engine's diagnostics are the only place it explains
*why* a dictionary failed to load. During the MDict investigation this cost
real time: the engine was reporting

```
MDict: parseCompressedBlock: plain: checksum not match
```

the whole while, and the tool showed nothing but `gd_scan_dicts -> 0`. The
reason a fixture was rejected had to be rediscovered by decoding the file by
hand. On device the same messages reach logcat normally, so the tool was blind
exactly where it is the primary debug surface — on the host, in CI.

## What Changes

- Install a Qt message handler in the smoke tool so engine diagnostics reach
  stderr, tagged and severity-labelled, instead of being dropped.
- Write to stderr rather than stdout, so diagnostic output can never
  interleave with the tool's own assertion lines that CI greps.
- This is tooling only: no engine behaviour, no app behaviour, no spec-level
  behaviour change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The smoke tool is a build-time diagnostic, not user-visible behaviour,
so no spec requirement changes. `.openspec.yaml` sets `skip_specs: true`.

## Impact

- `carve/smoke/main.cpp` — one `QCoreApplication` and one message handler.
- No change to what the tool asserts, to the engine, or to the app.
- CI output becomes louder on the stderr stream; existing assertions read
  stdout and are unaffected.
