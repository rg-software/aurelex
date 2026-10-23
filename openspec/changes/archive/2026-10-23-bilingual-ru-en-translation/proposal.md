# Proposal

## Why

Three of the four bilingual dictionaries exist (en→ru translation, en→ru
pairs, ru→en pairs). The fourth — ru→en translation — is the same `ili`
bridge walked the other way: RU synset → PWN synset, EN lemmas as
equivalents, the PWN gloss as the definition (verbatim, untranslated).
Probing confirms the bridge is clean in this direction: `хлеб` resolves to
2 RU synsets with natural-case definitions, linked to EN synsets with
natural-case lemmas (`Moscow`, `Russian_capital` keep their capitals, so no
lowercasing rule is needed on this side). POS labels stay in the target
language (English), per the convention the reader confirmed.

## What Changes

- A RU→EN resolver mirroring the EN→RU one: one card sense per linked EN
  synset (equivalents = EN lemmas verbatim, definition = PWN gloss,
  synonyms = fellow RU lemmas); unlinked RU synsets ship synonyms only.
- Example selection reuses `select_for_sense` unchanged on the flipped
  corpus view (pairs stay in source→target order, so the anchor always
  checks the second element; the flipped frequency counter is English).
- English POS section labels (target language); EN-side headword hygiene
  and the single-character rule transfer unchanged.
- RU pronunciation audio reuses the kaikki RU stage verbatim
  (`collect_records` gains the same language parameter `kaikki_headwords`
  already has).
- CLI: `--mode translation --source-lang ru` (universe: `--all-kaikki` on
  the RU snapshot). No new dependencies, no engine/app/boundary changes.

## Capabilities

### New Capabilities

<!-- none: this change adds a direction to an existing capability -->

### Modified Capabilities

- `bilingual-dictionary`: reverse-translation requirements (resolution,
  English definitions, article layout, EN-side examples, RU audio) plus a
  direction-aware translation provenance scenario.
