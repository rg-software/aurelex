## Why

A full English build of the current snapshot yields 884,316 cards, and a probe
found two blemishes a robust pipeline should not ship: 47 headwords appear twice
(one full card and one part-of-speech-only stub), and 1,101 cards carry no
definition at all. Both come from the same root cause — the snapshot is not
word-sorted, and the build only merges records that are *adjacent* in the file —
and dropping the definition-less cards naively would leave cross-references
pointing at headwords that are no longer there.

## What Changes

- Merge every source record for a headword into a single card, even when the
  records are not adjacent in the snapshot, so a headword is indexed once.
- Omit a card that has no definition (no gloss) — unless another emitted card
  links to it, in which case it is kept so the link resolves.
- Never leave a link dangling: a reference to a headword the dictionary does not
  contain is unlinked to plain text, and the case is counted.
- Report the three counts (headwords merged, definition-less cards omitted,
  references unlinked) in the build summary.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: the emitted cards gain a one-card-per-headword
  guarantee, a definition requirement, and a no-dangling-link guarantee, beyond
  the existing base-form and cross-reference requirements.

## Impact

- `scripts/kaikki-to-dsl.py`: headword selection detects split headwords; the
  render pass defers and merges them; card emission is collected and filtered
  before the dictionary text is assembled; the report gains counters.
- `scripts/tests/test_kaikki_to_dsl.py`: tests for merging, omission, the linked
  exception, and the absence of dangling references.
- The output for a given snapshot changes (fewer, merged cards); rebuild
  determinism is unaffected.
