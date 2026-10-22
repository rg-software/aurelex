# Tasks

## 1. Coverage gates (must pass before any builder)

- [x] 1.1 Run the core-5000 Dict A probe against the full-PWN denominator and record the linked-synset coverage in `docs/BILINGUAL-EXPERIMENT.md`; gate passes only if clearly above native ~11% — verify the results table has a filled core-5000 row
- [x] 1.2 Confirm the Tatoeba eng→rus funnel on the probe headwords (dedupe → rank → cap, keep-N per sense) and record kept-per-headword counts — verify every probe headword ships 1–3 shippable pairs or a documented reason for zero

## 2. Shared builder scaffolding

- [x] 2.1 Create the builder package skeleton under `scripts/` (headword list, DSL emitter reusing the reader-supported tag subset, dictzip writer, deterministic output) with a unit test that two runs on fixed inputs are byte-identical — verify the test passes
- [x] 2.2 Implement sample mode (bounded headword subset) and HTML preview rendering, with tests that re-runs produce the same sample — verify preview output matches the promoted probe samples' shape
- [x] 2.3 Document the builder CLI (inputs, caches, outputs) in the new docs section and verify every documented command runs as written

## 3. Dict A equivalents builder

- [x] 3.1 Implement PWN → `ili` → RuWordNet equivalent resolution grouped per RU synset, with unlinked senses counted (adverbs included) — verify counts against the probe's 215/215 on the 50-word set plus a unit test for the unlinked path
- [x] 3.2 Implement Russian definitions with the title-fallback chain and lowercase-only-if-fully-uppercase rule, plus Russian POS labels via `_RU_POS_LABELS` — verify `give` m3 renders `посвятить (предназначить, отдать)` and `[p]гл.[/p]`
- [x] 3.3 Implement per-sense equivalent cap and English-synonym secondary lines — verify the 8-per-group bound and syn line on the probe cards, with unit tests for cap and empty-synonym cases

## 4. Dict B example selector

- [x] 4.1 Implement Tatoeba acquisition (weekly exports or per-pair files: sentences + links join, eng→rus filter) with pinned dates recorded — verify pair count is within 5% of the probe's 831,236 on the same dump date
- [x] 4.2 Implement dedupe (one RU variant per normalized EN text) → rank (anchored-first via Dict-A equivalents, shortest-first; length ranks, never filters) → cap, with word-boundary matching on both sides — verify the `know` funnel (32,634 → 3 kept) and the `сдаваться` false-positive regression test
- [x] 4.3 Implement rarity-weighted anchoring preferring distinctive equivalents, with a unit test that a high-frequency-verb match loses to a distinctive match — verify on the probe's anchored-pair set
- [x] 4.4 Implement per-sense collapsible example zones (`[*]…[/*]`, one pair per sense, unanchored fallback as concordance) — verify zones sit under their sense and anchor-less senses still ship an example

## 5. Audio inheritance

- [x] 5.1 Wire the kaikki EN audio stage (planner + cache + `[s]` refs + sibling bundle layout) to run verbatim over Dict A headwords — verify a sample card references the same recordings as the kaikki EN card for that headword, and silence matches where EN is silent
- [x] 5.2 Add a test that every audio reference in a sample build resolves in its sibling bundle — verify zero unresolved references on the sample

## 6. Provenance, licensing, and docs

- [x] 6.1 Emit PWN attribution, RuWordNet non-commercial terms, Tatoeba CC BY attribution, and pinned source versions in metadata, about article, and sibling annotation, with the about card stating non-commercial use and distribution only — verify all three artifacts carry all four items on a sample build
- [x] 6.2 Update `docs/KAIKKI-CONVERSION.md` "Future" to point at the new capability and record the final source table — verify the matrix has no native column and links the new spec

## 7. End-to-end verification

- [x] 7.1 Build the full sample pair end-to-end (Dict A + Dict B + audio + provenance) and verify it imports through the existing folder import with articles rendering (equivalents, zoned examples, audio controls where vocal)
- [x] 7.2 Run the repo's relevant test suites (converter + new builder tests) and verify all pass with no changes to app/engine/boundary code

## 8. Recipes, CLI wiring, cache reuse

- [x] 8.1 Implement card-level example zones for pairs-only cards (headword + up-to-N pairs, no senses), with unit tests for zone placement, cap, and empty cases — verify a pairs card renders its zone and no sense numbering
- [x] 8.2 Implement the pairs-mode build path (headword universe, keep-N concordance selection, Tatoeba-only provenance, no audio) with an end-to-end fixture test asserting zero unresolved references — verify the fixture build imports structurally (dz decompresses, about + .ann present)
- [x] 8.3 Wire both modes into the CLI (translation flags + pairs flags + --all-lemmas), with tests for arg parsing, both modes, and error paths — verify --help and a sample run of each mode
- [x] 8.4 Write docs/builds/en-ru-wordnet.md and docs/builds/en-ru-tatoeba.md recipes and verify every documented command runs as written
- [x] 8.5 Extend docs/builds/cache.md with the bilingual cache layout (RuWordNet db, Tatoeba files, reuse rules) — verify each reuse claim against the actual default paths
