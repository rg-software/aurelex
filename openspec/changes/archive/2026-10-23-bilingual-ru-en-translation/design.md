# Design

## Context

See proposal.md — Why. Constraints carried over: the DSL reader's tag set,
single-digit `[mN]` tags, whole-word matching, stdlib-only runtime,
deterministic builds, flags-not-profiles (per the maintainability call:
the direction table stays a later refactor).

## Goals / Non-Goals

**Goals:**

- A ru→en translation dictionary with the same card discipline as en→ru:
  one card per headword, POS sections, lone-sense no counter,
  equivalents → definition → example → synonyms, empty headwords omitted.
- Maximal reuse: flipped corpus view, `select_for_sense`, headword hygiene,
  determinism and packaging paths run unchanged.

**Non-Goals:**

- No new ranking signals; EN equivalents rank by the existing English
  frequency counter.
- No lemmatization on either side (accepted limitation, recorded in
  `BILINGUAL-EXPERIMENT.md`).
- No audio for pairs (unchanged); RU audio only for the translation dict.

## Decisions

### D1. Walk the same bridge backwards

`get_senses(ru)` → RU synset → `.ili` → EN synsets. One card sense per
linked EN synset. EN lemmas ship verbatim (underscores → spaces, case
kept — the data is natural-case on this side); the PWN gloss ships
verbatim (no translation, no casing rule); fellow RU lemmas ship
lowercased as synonyms, mirroring the EN-side synonym rule. Unlinked RU
synsets resolve unlinked: synonyms only, no equivalents, counted against
coverage — the exact mirror of the adverb rule.

### D2. Anchor checks the second element, always

`select_for_sense` pairs are always (source, target): it anchors the
sense equivalents against the second element and falls back to the
shortest first element. On the flipped view that is EN-against-EN with
the English frequency counter — zero code change, covered by a flipped
unit test.

### D3. POS labels in the target language, again

The reader confirmed the convention: labels describe the headword for the
reader, who reads the target language. ru→en cards use English labels
(`noun/verb/adj/adv`); PWN POS letters map directly, and RU/EN synsets in
a bridge pair always agree.

### D4. Language-parameterize the snapshot scans, nothing else

`kaikki_headwords(snapshot, lang)` already takes the language; the audio
`collect_records` scan gets the same parameter. The kaikki planner,
bundler, and verifier run untouched on RU records.

## Risks / Trade-offs

- [Coverage is thesaurus-bound in both directions: RU headwords outside
  RuWordNet get no card] → counted as skipped, same as en→ru.
- [EN equivalents are unlemmatized PWN lemmas (`staff_of_life`)] →
  underscores become spaces; the rest ships verbatim, same discipline as
  the RU side.
