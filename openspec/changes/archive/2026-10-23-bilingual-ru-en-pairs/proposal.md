# Proposal

## Why

The pairs pipeline (`scripts/bilingual/`) bakes in one direction: the
headword universe comes from the kaikki EN snapshot, matching runs against
the English side of the Tatoeba pairs, and the markup roles assume the
Russian line is the translation. The machinery underneath — dedupe →
rank → cap, flat pairs cards, headword hygiene, case merging,
deterministic sampling — is direction-agnostic, but nothing wires it the
other way. A Russian→English example-sentences dictionary (same Tatoeba
export, kaikki RU snapshot as the universe) is the natural next step and
the test of whether the workflow is language-specific.

## What Changes

- The Tatoeba corpus carries both sides symmetrically: English and Russian
  frequency counters, an inverted index per side, and a `flipped()` view
  that swaps the pair order so every existing selection function runs
  unchanged (matching, dedupe, ranking, case merge, hygiene rules).
- New `--source-lang {en,ru}` CLI flag for pairs mode (default `en`);
  `ru` builds from the flipped view against the kaikki RU snapshot.
- `[ex]`/`[trn]` roles follow tuple position, so no rendering change: the
  source line is the example, the target line the translation.
- Provenance names the direction (`Sources.direction`, default `en-ru`).
- No engine, app, boundary, or import-path changes. No new dependencies.
- Out of scope: the reverse *translation* dictionary (ru→en equivalents —
  that needs an English-definitions source and its own change).

## Capabilities

### New Capabilities

<!-- none: this change generalizes an existing capability -->

### Modified Capabilities

- `bilingual-dictionary`: the "Examples-only cards" requirement (direction
  parameter: source line `[ex]`, target line `[trn]`), the "Pairs headword
  eligibility" requirement (universe is the source-language kaikki
  snapshot), and the "Provenance and licensing" requirement (direction-aware
  naming). Also corrects one stale clause: the title-fallback definition is
  sentence-cased, not lowercased (decided and implemented earlier).
