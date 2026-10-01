## Why

`kaikki-to-dsl.py --help` shows only the build options. The mode words —
`prefetch-audio`, `fetch-list`, `bundle-audio` — are dispatched by hand in
`main()` rather than through argparse subparsers (deliberately: the build is the
long-standing default and its flat options should not move behind a subcommand),
so argparse's usage and option list cannot mention them. A reader cannot tell a
mode word exists at all.

## What Changes

- List the modes and the `kaikki-to-dsl.py <mode> --help` pointer in the build
  parser's description, directly under the usage line, so they are visible before
  the option list rather than buried in the epilog notes.

## Capabilities

No spec-level behavior change: this is CLI help text; the modes' behaviour is
unchanged. `skip_specs: true`.

## Impact

- `scripts/kaikki-to-dsl.py`: `build_parser`'s `description`.
