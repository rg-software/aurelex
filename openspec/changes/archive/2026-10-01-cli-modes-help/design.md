## Context

`build_parser` uses `RawDescriptionHelpFormatter`, so its `description` prints
verbatim under the usage line. That is the most visible place to say the tool has
modes. The `Notes:` epilog already mentions the modes in prose, but only after
the option list.

## Decisions

### D1: A `Modes:` block in the description

Put a short list of the three modes and the `kaikki-to-dsl.py <mode> --help`
pointer in the description. No custom `usage=` string: the generated usage still
carries the build's required `--source-lang` and its options, which is the
information it is there for.

## Risks / Trade-offs

- **Duplicates what the epilog notes say.** Acceptable: the description is where
  a reader looks for "what can I run"; the epilog keeps the detailed how-to.
