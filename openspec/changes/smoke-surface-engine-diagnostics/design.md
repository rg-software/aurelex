## Context

`carve/smoke/main.cpp` defines a plain `int main()` with no
`QCoreApplication`. Qt's default message handler has nowhere to deliver
messages in that state on this platform, so every `qWarning`/`qDebug` from the
engine is dropped.

The engine explains load failures through exactly those messages, for example
`MDict: parseCompressedBlock: plain: checksum not match`. The tool therefore
reported only `gd_scan_dicts -> 0` for a fixture the engine had already
diagnosed precisely.

## Decision: install a message handler, write to stderr

`QCoreApplication` is constructed from `main`'s own `argc`/`argv` — Qt consumes
recognised options and ignores the rest, and the tool's positional arguments
are unaffected. A `qInstallMessageHandler` callback then prefixes each message
with its severity.

**stderr, not stdout.** The CI assertions grep the tool's stdout for lines such
as `gd_lookup("smoke") -> [1-9]` and `MARKERS: gdarticlebody=yes`. Engine
diagnostics on the same stream could interleave with those lines and turn a
passing assertion into a false negative. Keeping the streams separate means
diagnostics are always visible without touching the contract the assertions
depend on.

**No filtering.** Filtering by severity or category was considered and
rejected: the point is to stop hiding what the engine already decided was worth
reporting. If the volume becomes a problem in CI, that is a separate decision
with evidence behind it.

## Risks / Trade-offs

- **[Noisier CI output]** Engine chatter now appears on stderr. → Accepted;
  it is the information that was missing, and it does not affect the stdout
  assertions.
- **[`QCoreApplication` may reject an argument]** Qt removes options it
  recognises. → The tool takes positional paths and an optional word; a path
  that looked like a Qt option would already be a problem, and the smoke run
  uses absolute paths.
- **[Handler lifetime]** The handler is installed before `gd_init` and lives
  for the process; all engine output therefore goes through it.

## Verification

- Run the smoke tool and confirm a deliberately invalid fixture now reports the
  engine's own reason on stderr, where before it printed nothing.
- Confirm the existing CI assertions still pass: they read stdout, which is
  unchanged.
