## Context

`build()` derives everything from `header_name = args.name or "kaikki-<lang>"`
(`kaikki-to-dsl.py:2324`): the `#NAME` header, the about article's headword
(`About <name>`), and the output file names. The about article's body and
`write_annotation` are written separately, so their wording can drift. The user
hand-improved the `.ann` and wants builds to reproduce it from a title.

## Goals / Non-Goals

**Goals**

- A display title distinct from the output file name.
- One description template, shared by the about article and the `.ann`, so they
  cannot drift.

**Non-Goals**

- No change to what counts as an entry or to the file-name derivation.
- No localization of the description.

## Decisions

### D1: Title defaults to the output name

`--title` is optional and defaults to `--name` (itself defaulting to
`kaikki-<source>`), so existing invocations are unchanged. `#NAME`, the about
headword, and the description heading use the title; the `.dsl.dz`, `.files.zip`
and `.ann` names keep using the output name.

### D2: One description builder

`description_lines(title, language_name, language_code, dump_date, card_count)`
returns the plain-text description lines: the title, a blank, the derivative/
snapshot line, the "See also" reference, a blank, and the license, language and
entry count. `write_annotation` writes those lines verbatim; the about article
wraps each non-empty line in `[com]…[/com]` under the `About <title>` headword
and appends the icon legend. The `.ann` and the about body therefore carry the
same facts by construction.

### D3: `#NAME` is the title, the file names are the output name

The `#NAME` header is what a reader shows in its dictionary list, so it is the
title. Bundles and annotations are found by the dictionary *file* name, so those
keep the output name. The two are independent, which is what lets a nice display
name coexist with a clean file name.

## Risks / Trade-offs

- **A title with newlines or quotes** would corrupt the header/description;
  `header_arg` already sanitises quotes for `#NAME`, and the description is plain
  text, but a title containing a newline is not defended against. Acceptable for
  a CLI-supplied display name.
