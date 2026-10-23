# Proposal

## Why

Reviewing the built pairs dictionary against the archived `bilingual-dictionary`
spec turned up three mismatches between the spec and the article shape that
actually works: the spec mandates a single collapsible zone per card, but pairs
*are* the whole article, so every card would render as a lone `[+]` button;
nothing marks the Russian line as a translation; and junk headwords (stray
quotes, suffix fragments, bare numbers) and case-duplicate cards
(`maduro`/`Maduro` with identical bodies) have no rule. The builder already
implements the corrected behavior (verified through the real reader); this
change protocols it.

## What Changes

- Examples-only cards render flat `[ex]`/`[trn]` pairs with no zone and no
  sense numbering (MODIFIED requirement).
- New headword eligibility rule for pairs dictionaries (ADDED requirement):
  a headword must start with a Unicode letter; headwords differing only in
  case merge into one card, keeping the lowercase form when the pairs spell
  it lowercase and the capitalized form otherwise; headwords with no pairs
  are omitted.
- No engine, app, boundary, or import-path changes. No new dependencies.

## Capabilities

### New Capabilities

<!-- none: this change only corrects an existing capability -->

### Modified Capabilities

- `bilingual-dictionary`: the "Examples-only cards" requirement (flat pairs
  instead of a collapsible zone) plus a new headword-eligibility requirement
  for the pairs dictionary.
