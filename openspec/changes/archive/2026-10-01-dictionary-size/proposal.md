## Why

A produced dictionary says nothing about how big it is. Lingvo dictionaries
report it (the familiar "Total: N headings / M entries"), and it belongs with the
provenance in the about article and the sibling annotation so a user can see the
size without a lookup. "Headings" vs "entries" is the distinction between
headword lines and cards (one card can carry several headword lines, e.g. with
inflected forms); the card count is the meaningful total for us.

## What Changes

- State the number of entries (headword cards) in the about article and in the
  sibling `.ann` annotation.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: a new requirement that the about article and the
  annotation state the dictionary's size.

## Impact

- `scripts/kaikki-to-dsl.py`: the about article gains an entries line;
  `write_annotation` takes the card count and reports it.
- `scripts/tests/test_kaikki_to_dsl.py`: assert the count appears in both.
