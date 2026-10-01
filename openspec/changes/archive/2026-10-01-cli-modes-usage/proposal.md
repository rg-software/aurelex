## Why

The `Modes:` block added to the build parser's description is below the
auto-generated `usage:` line, which lists only build options — so the very first
line of `--help` still does not say the tool takes a mode word. A reader who
reads the usage line (as most do) still cannot tell a command exists.

## What Changes

- Give the build parser an explicit `usage` that names the mode word:
  `kaikki-to-dsl.py [<mode>] [options]`. The options stay listed in the OPTIONS
  section as before; the description's `Modes:` block says what the modes are and
  that no mode word builds a dictionary.

## Capabilities

No spec-level behavior change: CLI help text only. `skip_specs: true`.

## Impact

- `scripts/kaikki-to-dsl.py`: `build_parser`'s `usage`.
