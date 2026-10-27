# Proposal

## Why

The app already ships offline bilingual dictionaries for En↔Ru (translation + sentence-example pairs) and a monolingual Japanese dictionary with Japanese UI localization, but there is no offline translation path touching Japanese. Adding En↔Ja and Ja↔Ru closes that gap for Japanese learners and for Ru↔Ja lookup without reimplementing any dictionary format.

## What Changes

- **En→Ja / Ja→En translation dictionaries** built from Japanese WordNet (bond-lab `wnja`, pinned release) joined on Princeton WordNet synset IDs — the same sense-aligned bridge the En↔Ru dictionaries use via RuWordNet `ili`, but with JaWN sharing PWN IDs directly.
- **Ja→Ru / Ru→Ja translation dictionaries** built through a PWN-ID pivot: JaWN synsets ↔ PWN IDs ↔ RuWordNet `ili` links. Equivalents and definitions stay in the target language (Japanese definitions from JaWN, Russian from RuWordNet, English from PWN glosses verbatim).
- **Sentence-example dictionaries for all four directions** (En↔Ja, Ja↔Ru) from Tatoeba per-pair exports (`eng-jpn`, `jpn-rus`), reusing the existing dedupe → rank → cap selection with a Japanese-aware matcher (CJK substring discipline, no word-boundary assumption).
- **Per-sense anchored examples** for the translation dictionaries from the same Tatoeba pairs, with rarity-weighted anchoring against the sense's own equivalents and concordance fallback, as today.
- **Audio + transcription reuse verbatim** from the existing kaikki snapshots: English headwords from EN, Japanese headwords from JA, Russian headwords from RU. Silent where the monolingual card is silent.
- **Import-ready deterministic packaging** unchanged: `.dsl.dz` + sibling resource bundle + `.ann`, `#INDEX_LANGUAGE` / `#CONTENTS_LANGUAGE` naming the direction, byte-identical rebuilds, no app / engine / `gd_*` boundary change.
- **Catalog + docs**: new `catalog/source.json` entries (translation + pairs for each direction) and `docs/builds/` recipes with pinned versions; Japanese WordNet attribution (BSD-like + link-back) recorded alongside the existing PWN / RuWordNet / Tatoeba / kaikki credits.

## Capabilities

### New Capabilities

- None — the behavior extends the existing bilingual capability; no new durable system behavior is introduced.

### Modified Capabilities

- `bilingual-dictionary`: extend equivalent resolution, definitions, article layout, example selection/matching, audio/transcription reuse, packaging headers, and provenance beyond the current En→Ru / Ru→En scope to En↔Ja and Ja↔Ru (new thesaurus source, pivot join, Japanese tokenization, Japanese POS labels, new Tatoeba pairs, new attribution).

## Impact

- `scripts/bilingual/` — equivalents backend (JaWN source + PWN-ID pivot), Tatoeba acquisition/matching for `eng-jpn` / `jpn-rus` (Japanese tokenizer), CLI `--source-lang ja` (+ direction validation), DSL/POS/provenance for Japanese, audio/transcription language wiring.
- `scripts/tests/test_bilingual_to_dsl.py` — new fixtures/cases for JaWN resolution, pivot joins, Japanese matching, headers/provenance.
- `docs/BILINGUAL-BUILDER.md`, `docs/BILINGUAL-EXPERIMENT.md`, `docs/builds/` (new `en-ja-wordnet.md`, `ja-en-wordnet.md`, `ja-ru-wordnet.md`, `ru-ja-wordnet.md` + Tatoeba pair recipes) — sources, pins, yields.
- `catalog/source.json` — new entries (translation + pairs × 4 directions); published via the existing `publish-catalog.ps1` flow.
- No app, engine, submodule, patch-set, or `gd_*` boundary change; no new runtime dependency in the app (the `wn`/JaWN tooling is build-time only, like `ruwordnet`).
