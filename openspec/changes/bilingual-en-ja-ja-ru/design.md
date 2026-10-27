# Design

## Context

See `proposal.md` for why. Current state: `scripts/bilingual/` builds En→Ru / Ru→En only — RuWordNet `ili` bridge (`equivalents.py`), Tatoeba `eng/rus/eng-rus_links` acquisition with English word-boundary matching (`tatoeba.py`), `--source-lang {en,ru}` CLI, Russian/English POS labels, kaikki EN/RU audio verbatim, provenance naming PWN + RuWordNet + Tatoeba. Japanese WordNet (`bond-lab/wnja`, PWN-shared IDs) and Tatoeba `eng-jpn` / `jpn-rus` exports make the same pipeline viable for four more directions with no app/engine change.

## Goals / Non-Goals

**Goals:**
- Four new dictionaries (translation + pairs each: En↔Ja, Ja↔Ru) through the existing pipeline shape with pinned, reproducible inputs.
- Japanese matching that respects spaceless text; POS/attribution/audio correct per direction.

**Non-Goals:**
- No new DSL tags, reader, app, engine, or boundary changes; no JMdict/EDICT or aligner work — WordNet-family + Tatoeba only, same as En↔Ru.
- No catalog app-behavior change (new entries ride the existing manifest flow).

## Decisions

- **JaWN source: pinned `wnja` 2.x WN-LMF via the `wn` module (build-time only, like `ruwordnet`).** Alternative considered: 1.1 `wnjpn.db.gz` sqlite — older (2010, ~5% error disclaimer), frozen schema. `wn` + `omw-en` gives current IDs matching PWN; pin the release tag + record it in provenance. Fallback: small ID→lemmas/definition table extracted once, so full builds stay offline.
- **En↔Ja join on shared PWN ID directly; Ja↔Ru join as PWN-ID pivot (JaWN ↔ PWN ↔ RuWordNet `ili`).** Alternative considered: direct Ja–Ru thesaurus — none exists; pivot reuses two pinned bridges with no new fuzzy matching. Unlinked senses keep the existing counted-but-unrendered discipline.
- **Tatoeba acquisition generalized to per-pair files** (`{src}_sentences`, `{tgt}_sentences`, `{src}-{tgt}_links`), pinned export date. Verified to exist: `eng-jpn_links` (~1.4 MB bz2) and `jpn-rus_links` (~200 KB bz2) — Ja↔Ru pairs will be thin; pairs dictionaries keep the keep-N cap so thin is still shippable.
- **Japanese matching: substring (no `\w` boundaries), CJK `。` sentence splitting, Japanese-side frequency counter.** Reuses the `dictionary-conversion` CJK discipline (`Example qualification` scenarios). Single-character headwords stay example-free in all languages (existing rule generalized) — for Japanese this avoids every-sentence-matches-kanji noise at the cost of single-kanji examples.
- **Labels/audio/provenance reuse, not reinvention.** Target POS labels from the existing kaikki profiles (`_JA_POS_LABELS`, `_RU_POS_LABELS`, English verbs/nouns as today); audio + `[t]` transcription from the source-language kaikki snapshot verbatim (`en`/`ja`/`ru` via existing `lang` params); `#INDEX/#CONTENTS_LANGUAGE` from a direction→language table extended with Japanese; provenance `Sources` gains `wnja` version + direction-aware kind/pair labels, JaWN link-back included, non-commercial line only when RuWordNet contributed.
- **CLI: `--source-lang {en,ru,ja}` + `--target-lang` (or direction) with validation; `--tatoeba-dir` layout unchanged (files discovered by pair name).** Keeps `--all-kaikki` universe semantics (source-language snapshot) and `--resolve-cache` keyed by thesaurus fingerprints (now two files for pivot builds).

## Risks / Trade-offs

- [Pivot coverage is a product of two hit rates] → Mitigation: probe first (core-word sample per direction, report linked/total like the 84.5% En↔Ru gate); ship pairs dictionaries regardless since they need no thesaurus.
- [`jpn-rus` Tatoeba slice is ~25× smaller than `eng-rus`] → Mitigation: concordance fallback already guarantees cards still ship; report pairs-per-headword in the build log.
- [Single-kanji headwords get no examples by the singles rule] → Mitigation: accepted (cards still ship equivalents); revisit only with a frequency-gated matcher, out of scope here.
- [JaWN definitions translated from English may mismatch the synset] → Mitigation: eyeball the sample preview (same gate as En↔Ru); definitions are subordinate text under equivalents, never the lookup answer.
- [Anchor recall ~19% makes the concordance fallback load-bearing] → Mitigation: fallback stays but never repeats a source or translation within a card (measured 2026-10-25: 87% en-ja / 81% en-ru headwords have no anchor at all). Proper fix — lemmatization plus kana normalization — needs a morphological dictionary outside the stdlib-only runtime contract; tracked as tech debt in `docs/BILINGUAL-EXPERIMENT.md`, not this change.
- [Two thesaurus pins → stale-pivot drift] → Mitigation: provenance pins both versions; resolve-cache key includes both file fingerprints.

## Migration Plan

- Additive only: new builder flags, new `docs/builds/*.md` recipes, new `catalog/source.json` entries published through `publish-catalog.ps1`. No migration, no rollback beyond not publishing; existing En↔Ru outputs byte-identical (no shared code-path behavior change except generalized helpers with same En↔Ru results, covered by existing tests).
