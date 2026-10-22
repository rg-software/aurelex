# Proposal

## Why

The kaikki converter builds monolingual dictionaries only, by decision: native
kaikki `translations[]` tables top out at ~4–11% sense-aligned coverage and
were measured and rejected in every direction (see `docs/KAIKKI-CONVERSION.md`
"Why monolingual only" and `docs/BILINGUAL-EXPERIMENT.md`). Probes have since
shown a viable route to En→Ru translation dictionaries — sense-aligned
equivalents via Princeton WordNet + RuWordNet `ili` links, sense-anchored
example sentences via Tatoeba, pronunciation audio inherited from the kaikki EN
build — with article shape, selection rules, and coverage ceilings already
measured on samples. This change protocols that approach as a new capability so
the builder scripts can be written against a spec.

## What Changes

- New `scripts/` builders (one per source job) that produce offline En→Ru DSL
  dictionaries (`.dsl.dz` + sibling resource bundle) through the existing folder
  import — no app, engine, or boundary changes:
  - equivalents from PWN synsets bridged through RuWordNet `ili` links
    (Russian definitions, Russian equivalents, English synonyms);
  - example sentences from Tatoeba eng→rus pairs, selected per sense by the
    decided dedupe → rank → cap rule;
  - pronunciation audio reused from the kaikki EN build's audio stage verbatim.
- Article layout for translation cards: senses numbered by RU synset, L2
  definitions, `[trn]` equivalents, English synonyms secondary, one anchored
  example per sense in a per-sense collapsible zone, Russian POS labels.
- Provenance and licensing per dictionary: PWN attribution, RuWordNet
  non-commercial terms, Tatoeba CC BY 2.0 FR attribution, pinned source
  versions. Outputs are for non-commercial use and distribution only, not shipped
  entries.
- Docs: the experiment note (`docs/BILINGUAL-EXPERIMENT.md`) stays the probe
  record; the "Future" matrix in `docs/KAIKKI-CONVERSION.md` is updated to point
  at the new capability once built.

## Capabilities

### New Capabilities

- `bilingual-dictionary`: building offline En→Ru translation dictionaries from
  WordNet-family equivalents + Tatoeba sentences + inherited kaikki audio —
  source acquisition, sense-aligned equivalent resolution, per-sense example
  selection (dedupe → rank → cap), translation article layout, deterministic
  import-ready packaging, and provenance/licensing.

### Modified Capabilities

<!-- none: dictionary-conversion (monolingual) and dictionary-management (folder
     import) are untouched; the new builders consume the existing import path
     unchanged. -->

## Impact

- `scripts/` — new builder scripts + tests (standard library + `ruwordnet`
  tooling at build time; no Android/app dependency).
- `docs/KAIKKI-CONVERSION.md` — "Future" section points at the new capability.
- No engine, app, boundary, or catalog changes. No new runtime dependency.
- Data dependencies (desktop build-time only): NLTK `wordnet`, `python-ruwordnet`
  sqlite (~80 MB), Tatoeba weekly exports, kaikki audio cache.
