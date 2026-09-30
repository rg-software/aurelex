## Why

A sense that names the same related headword in both `alt_of` and `form_of`
(e.g. `[[ho]]` for `ho ho`) has that target wrapped in a link twice, producing
`[ref][ref]ho[/ref][/ref]`. The second wrap lands inside the link the first one
inserted. The doubled markup is malformed, and it defeats the no-dangling-link
safety net: the link's text contains `[ref]`, so the target is not recognised and
the card can end up pointing at a headword that was never emitted. Two cards in
the current full build are affected.

## What Changes

- Emit a related-headword link at most once per gloss, however many relations
  (`alt_of`, `form_of`) name the same target.
- When an absent-target link is unlinked, strip any link markup from what
  remains, so a malformed/ nested link cannot leave a `[ref]` behind.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: the linked-related-headwords requirement gains the
  guarantee that a target is linked once.

## Impact

- `scripts/kaikki-to-dsl.py`: `_link_form_targets` de-duplicates targets;
  `unlink_absent_refs` strips residual link markup when it unlinks.
- `scripts/tests/test_kaikki_to_dsl.py`: tests for the single link and the
  markup-free unlink.
