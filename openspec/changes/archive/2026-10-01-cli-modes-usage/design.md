## Context

`build_parser` relies on argparse's generated usage, which is derived from its
options and so cannot mention the hand-dispatched mode words. The description's
`Modes:` block is right below the usage line, but the usage line itself is the
first thing read.

## Decisions

### D1: An explicit `usage` naming the mode word

`usage="kaikki-to-dsl.py [<mode>] [options]"`. The build's required
`--source-lang` and its options stay in the OPTIONS list; the usage line's job is
to say the shape of a command line, and the shape allows a mode word. The Modes
block in the description gives the specifics.

## Risks / Trade-offs

- **The usage no longer enumerates the build options.** They are one line below in
  OPTIONS, and the previous behaviour (no mode visible anywhere near the top) was
  the complaint.
