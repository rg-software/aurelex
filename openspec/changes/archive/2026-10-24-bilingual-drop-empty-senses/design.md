# Design

## Context

See proposal.md — Why. Card assembly (`build_sample`) turns resolved
senses into DSL senses; the filter belongs there, not in the resolver
(coverage counts resolved senses) and not in the emitter (which stays a
dumb renderer of what it is given).

## Goals / Non-Goals

**Goals:**

- No numbered section without a translation answer: a sense needs at
  least equivalents or a definition to be rendered.
- en-ru output provably unchanged (zero such senses in the full build).

**Non-Goals:**

- No change to example selection: an example attached to a dropped sense
  goes with it (it was a concordance fallback or an anchor for
  synonyms-only content).
- No change to `skipped_empty` semantics beyond the natural consequence:
  a headword with only undisplayable senses gets no card.

## Decisions

### D1. Filter at assembly, count at resolve

`resolve_words` still returns unlinked senses and the report still counts
`synsets`/`synsets_linked` exactly as before. `build_sample` skips senses
with `not equivalents and not definition` when appending DSL senses. A
headword whose every sense is skipped gets no card via the existing
`skipped_empty` path.

### D2. Symmetric across directions

The en-ru dictionary contains no such senses (verified on the full
35,676-card build), so the rule is provably a no-op there: the published
file must rebuild byte-identical. Verified by rebuilding the showcase
sample and diffing bytes.

## Risks / Trade-offs

- [RU-only synonyms of unlinked synsets disappear from articles] → they
  are monolingual content in a bilingual dictionary (no translation
  exists in the thesaurus); accepted, and still counted in coverage.
- [A headword with only unlinked senses loses its card] → it joins
  `skipped_empty`; previously it rendered synonym/example shells.
