# Design

## Context

See proposal.md - Why. Constraints shaping the approach:

- `python-ruwordnet` bundles everything Dict A needs in one sqlite (~80 MB,
  2021 db: 59,905 RU synsets, 21,138 linked EN synsets): RU lemmas, RU
  definitions/titles, EN synonyms + glosses, and the `ili` join table. No
  example tables exist anywhere in it (verified against the schema), so
  examples can only come from Tatoeba.
- The EN side of `ili` covers ~18% of PWN (21,138 of ~117k synsets). That is
  the hard ceiling on equivalent coverage; common words overstate it (50-word
  probe: 100% linked). The core-5000 probe against full PWN measures the real
  number before any full build.
- Tatoeba ships pre-joined per-pair files (`eng-rus_links.tsv.bz2` ~5 MB plus
  per-language sentence files), so Dict B needs no global dump: ~45 MB total
  for eng→rus. 831,236 pairs measured; selection (not coverage) is the problem.
- kaikki's DSL reader tag set already covers everything the cards need
  (`[p] [mN] [trn] [ex] [*]…[/*] [s]`); the kaikki EN build's audio planner,
  cache, and bundle layout are reused verbatim. Russian POS labels come from
  the repo's own `_RU_POS_LABELS` (`scripts/kaikki/profiles.py:281`).
- Non-commercial constraint is structural: RuWordNet thesaurus (NC, no
  research-institution clause) + Tatoeba CC BY (attribution) + PWN (attribution)
  ⇒ outputs are for non-commercial use and distribution only, never catalog entries. BabelNet stays out
  (research-institution-only + NC).

## Goals / Non-Goals

**Goals:**

- One builder per source job sharing a headword list, a DSL emitter, and the
  sample → preview → measure habit; Dict B's selector doubles as the Dict A
  example ranker (anchoring).
- Reuse, not reinvention: kaikki audio stage, DSL tag subset, POS labels,
  dictzip writer, preview pattern.

**Non-Goals:**

- Full-PWN denominator tooling beyond what the core-5000 probe needs; no NLTK
  dependency unless the probe demands EN examples (it should not — they are
  English-only).
- Word-alignment models (`fast_align` et al.): rarity-weighted anchoring plus
  eyeball is the mechanism; statistical alignment is a separate project.
- Any change to the app, engine, boundary, import path, or catalog; any new
  runtime dependency.

## Decisions

### D1. RuWordNet `ili` is the only equivalent bridge; native tables are out

Native kaikki `translations[]` were measured (en→ru 3.9%, ru→en 10.7%, ja→en
10.8% aligned) and rejected everywhere — sparse and fuzzy-matched. `ili`
links are sense-aligned by construction and bilingual by definition (RU synset
↔ EN synset). *Alternative rejected:* OMW-extended Russian — Wiktionary-derived,
inherits the native quality caveat. *Alternative rejected:* BabelNet — license
blocker (see Context).

### D2. Senses are numbered by RU synset; L1 gloss is build metadata

One EN synset routinely maps to several RU synsets (e.g. give "devote" →
ОТДАТЬСЯ + ПОСВЯТИТЬ groups), so the RU synset is the sense unit and the L1
gloss cannot be displayed without lying about granularity. The gloss stays in
build logs for debugging. *Alternative rejected:* numbering by EN synset with
merged equivalents — flattens distinct Russian construals into one soup.

### D3. L2-first card: RU definition → equivalents → EN synonyms → zoned example

The reader disambiguates in Russian; English survives only as secondary
synonyms and inside examples. Examples go in per-sense `[*]…[/*]` zones
(kaikki convention; the removed learner mode did the same), keeping long cards
like `give` scannable. *Alternative rejected:* always-visible examples — walls
of text on multi-sense cards; locality (zone under its sense) matters more than
visibility.

### D4. Tatoeba selection is dedupe → rank → cap, with anchoring as rank

One RU variant per EN sentence (no reason to ship several translations of one
sentence); anchored-first (Dict-A equivalent in RU side), shortest-first; keep
N per sense (probe: 1) / per headword (probe Dict B: 3). Length ranks, never
filters; anchor-less senses fall back to concordance pairs; kaikki EN examples
never qualify (English-only, sense-unaligned). Rarity-weighting (prefer
distinctive equivalents like `посвятить` over `уйти`) counters substring
false-positives; RU-side matching is word-boundary, same as EN. *Alternative
rejected:* statistical aligner — cost without need at this density.

### D5. Audio is inherited, not planned

Dict A headwords are English lemmas, so the kaikki EN audio stage already
decided their recordings. Reuse it verbatim (planner + cache + `[s]` refs +
bundle layout); silence lands exactly where the monolingual cards are silent.
*Alternative rejected:* extracting refs from the published `.dsl.dz` — couples
the builder to a build artifact instead of the pipeline that produced it.

### D6. Pairs mode is a separate dictionary, not a degraded translation one

The sentence-example dictionary has its own cards (headword + up-to-N pairs in
one zone, no senses, no `ili`), its own provenance (Tatoeba only), and no
audio. It shares the selector, the zone convention, and the packaging with Dict
A, and its headword universe is the same EN lemma list — but it is a second
output, verified and published separately. *Alternative rejected:* folding pairs
into translation cards without equivalents — muddies the article contract
(equivalents are the answer) and couples two release cadences.

### D7. Sample → preview → measure gates every stage

Core-5000 (Dict A, full-PWN denominator via NLTK if the bundled EN subset
proves insufficient) and the 50-word Tatoeba funnel are the gates; full builds
run only after both pass. Probe scripts live outside the repo tree; only
promoted builders land in `scripts/` with tests.

## Risks / Trade-offs

- [`ili` covers ~18% of PWN; the real representative coverage is unmeasured] →
  core-5000 probe with full-PWN denominator before any full build; a low number
  stops the project with a recorded negative result.
- [Anchoring misattaches ( substring `давать` in `сдаваться`; `уходить` rendering
  *leave* under *give*)] → word-boundary matching + rarity weighting; residual
  noise is eyeballed per sample, never silently shipped.
- [RU definitions/titles occasionally empty or terse; proper nouns lowercased
  with everything else] → title fallback chain; case heuristic documented as
  approximate in the probe record.
- [Tatoeba one-to-many sentence variants; 32k pairs for `know`] → dedupe + cap
  bound article size by construction; full-dict size scales with headwords, not
  pairs.
- [Outputs are for non-commercial use and distribution only] → stated in the about card;
  never enter the catalog pipeline; BabelNet-shaped licensing questions cannot
  arise by construction.

## Migration Plan

Not applicable — additive desktop-only builders, no existing behavior changes,
no rollout. Rollback is deleting the scripts and the change. If the core-5000
probe fails the gate, the change is abandoned and the negative result is
recorded in `docs/BILINGUAL-EXPERIMENT.md`.

## Open Questions

None that change specs, approach, or tasks. Tuning parameters (per-sense
equivalent cap, keep-N counts, preferred-length bound, rarity function) are
settled on samples during implementation within the spec'd bounds.
