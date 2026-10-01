## Why

The about article and the sibling annotation show the dictionary's name, but the
name is also the output file name, so a human-friendly display name (with spaces
or title case) cannot be used without ugly file names. The annotation also has no
shared template with the about article, so the two drift; a hand-improved
annotation cannot be reproduced by a build.

## What Changes

- Add a `--title`: a display name separate from the output name, defaulting to
  it. The title is used for the dictionary's name metadata, the about article's
  headword, and the description heading; output file names (dictionary, bundle,
  annotation) keep using the output name.
- Generate the about article's body and the `.ann` from one description template:
  the title, a canned "derivative work of Wiktionary / kaikki.org, snapshot
  <date>" line, the wiktextract reference, the license, the language, and the
  entry count.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: a new title/name requirement, and the
  provenance-and-attribution requirement now ties the about article and the
  annotation to the same description.

## Impact

- `scripts/kaikki-to-dsl.py`: `--title`, a shared description builder used by the
  about article and `write_annotation`, and `#NAME` from the title.
- `scripts/tests/test_kaikki_to_dsl.py`: title/name separation and the shared
  description.
- `docs/KAIKKI-CONVERSION.md`: the naming note.
