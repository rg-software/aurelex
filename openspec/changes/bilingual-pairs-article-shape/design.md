# Design

## Context

See proposal.md — Why. The builder (`scripts/bilingual/`) already implements
the corrected behavior; this change protocols it. Constraints carried over
from the archived change: the DSL reader's tag set, the word-boundary matching
discipline, the Tatoeba index for full-dictionary scale.

## Goals / Non-Goals

**Goals:**

- Spec text that matches the verified article shape, so the next review starts
  from the truth.
- No behavior change: code and tests already implement and cover every
  requirement below (39 bilingual unit tests green, smoke-verified article).

**Non-Goals:**

- No article stripping (`A major`, `The Hague`, `a priori` are legitimate
  headwords — verified against the snapshot; stripping would corrupt them).
- No allowlists; no per-word exceptions.

## Decisions

### D1. Flat pairs, no zone

A pairs card with a zone is a lone `[+]` button — the zone hides 100% of the
article. Flat `[ex]`/`[trn]` lines keep everything one glance away on cards
capped at keep-N pairs.

### D2. Russian lines are `[trn]`, not `[ex]`

The reader styles them distinctly, which is the point: in a bilingual article
the translation should look like a translation. Same convention already
applies to Dict A sense examples and equivalents.

### D3. Letter-start rule instead of a junk list

192 of 46,099 built cards (0.4%) were junk, all sharing one property: the
headword does not start with a Unicode letter. One predicate kills stray
quotes, suffix fragments and bare numbers without maintaining a list. The cost
(a handful of clippings like `'cause`) is acceptable — they stay reachable
through full-text search.

### D4. Case-fold merge keyed on the card body

Case variants necessarily share identical bodies (matching is
case-insensitive), so separate cards can never differ in content — merging
loses nothing. The lowercase form wins exactly when the pairs spell it
lowercase (common nouns surface lowercase somewhere, mid-sentence, so
sentence-initial capitals do not fool it); otherwise the capitalized form
stands (proper nouns never occur lowercase). Between several capitalized
forms the alphabetical one wins; the body is identical either way.

## Risks / Trade-offs

- [A proper noun that only ever appears sentence-initially in its pairs is
  lowercased] → rare by construction (needs *every* pair to open with it);
  accepted, documented in the experiment note.
- [Clippings (`'cause`) lose their cards] → findable via full-text search;
  accepted.
