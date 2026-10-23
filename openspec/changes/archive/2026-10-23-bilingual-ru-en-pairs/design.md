# Design

## Context

See proposal.md — Why. Constraints carried over: the DSL reader's tag set,
the word-boundary matching discipline, the Tatoeba index for
full-dictionary scale, stdlib-only runtime, deterministic builds.

## Goals / Non-Goals

**Goals:**

- A ru→en pairs dictionary from the same pinned Tatoeba export, same
  article shape, same hygiene rules, same determinism guarantees.
- Minimal new machinery: one symmetric corpus view, one CLI flag, one
  provenance field. Every ranking/selection function reused verbatim.

**Non-Goals:**

- No reverse translation dictionary (equivalents direction) — separate change.
- No audio for pairs (as before — per-contributor Tatoeba licenses).
- No new tokenizer beyond a Russian word regex; no lemmatization (accepted
  limitation, recorded in `BILINGUAL-EXPERIMENT.md`).

## Decisions

### D1. Flipped corpus view instead of mirrored functions

`Corpus` gains the other side's frequency counter and inverted index
(`eng_freq`, `index_ru`, built in the same acquisition pass) plus a
`lang` marker selecting the tokenizer. `flipped()` returns a view with the
pair order swapped, the counters and indexes swapped, and `lang="ru"` —
so `pairs_for`, `select`, `_choose_case`, `build_pairs`, the letter-start
rule and the single-character rule all run unchanged. One code path, two
directions; a direction bug fix lands in both.

### D2. Markup roles follow tuple position

`emit_card` already renders each pair as `[ex]`first/`[trn]`second. On the
flipped view the first element is the Russian sentence, so ru→en cards
come out as `[ex]`Russian example / `[trn]`English translation with zero
rendering changes. Same for the HTML preview (positional).

### D3. Case merge and hygiene are script-agnostic

`str.isalpha()` accepts Cyrillic, so the letter-start rule needs no change.
The case-merge heuristic (lowercase wins when the pairs spell it lowercase)
is about usage, not script: Russian common nouns surface lowercase
mid-sentence exactly like English ones; proper nouns never do. The
single-character rule transfers as well (the article/noise argument holds
for any one-letter token).

### D4. Direction-aware provenance, default en-ru

`Sources.direction` (`"en-ru"` default, so every existing build is
unaffected) drives the kind strings: "a Russian-English
example-sentences dictionary", "Tatoeba rus-eng pairs". The license block
is unchanged (Tatoeba CC BY 2.0 FR either way).

## Risks / Trade-offs

- [Russian morphology defeats whole-word matching more often than English
  (inflected anchors invisible, e.g. уровня vs уровень)] → the accepted
  anchoring limitation, now symmetric; no new machinery.
- [Kaikki RU headword list includes inflected forms?] → `kaikki_headwords`
  already filters non-lexical/inflected records per language; the ru→en
  universe gets the same treatment as en→ru.
