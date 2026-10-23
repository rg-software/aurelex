# Bilingual dictionary experiment (En→Ru)

Dated 2026-10-22. Status: **outline + probes, not a build**. This note records the
experiment plan for two En→Ru dictionaries and the numbers that will decide
whether either becomes an OpenSpec change. It is deliberately not a spec: no
implementation runs until a probe says "viable" (see [Exit criteria](#exit-criteria)).

Background (measured, see `KAIKKI-CONVERSION.md` "Why monolingual only"): native
kaikki `translations[]` tables top out at ~11% sense-aligned coverage (ru→en
10.7%, ja→en 10.8%, en→ru 3.9%) and are rejected as a source everywhere. The
remaining plan is one source per job: WordNet-family data for equivalents,
Tatoeba for sentences, RuWordNet for the Russian bridge OMW v1 lacks.

Presumption checked and corrected: vanilla Princeton WordNet alone yields **zero**
Russian — it is English-only, and OMW v1 (28 wordnets) contains **no Russian and
no German**. Dict A below needs RuWordNet for the Russian side.

## Dict A: equivalents (PWN + RuWordNet `ili`)

**Inputs** (all downloadable today): NLTK `wordnet` (Princeton) + `pip install
ruwordnet` then `ruwordnet download` (~80 MB sqlite; RuWordNet v2.0/2021: 59,905
synsets, 154,111 senses; nouns/verbs/adjectives; each synset carries `ili`, the
link to the English WordNet synset, and the package bundles the linked English
subset).

1. **Headwords:** English lemmas from PWN. Probe on the ~5,000 **core** senses
   (Boyd-Graber list) — frequent, reviewable, representative.
2. **Bridge:** PWN synset → `ili` → RuWordNet synset(s) → Russian member lemmas.
   Sense alignment is inherited from the synset grouping; no fuzzy sense-key
   matching. en→ru is reverse-`ili` lookup over the same link set.
3. **Coverage gate:** count English synsets with no `ili` link, do not guess.
   Ceiling ≈ 60k/118k synsets (~51%); the probe measures the actual hit rate on
   the core sample.
4. **Render (DSL, existing tags only):** headword + POS; per sense: English gloss
   as heading (learner-style), Russian equivalents as `[trn]`, PWN English
   examples kept as untranslated usage `[ex]` or dropped — decide on the sample.
   Keep phrases (RuWordNet has many; DSL handles multi-word headwords).
5. **Provenance card:** PWN attribution + RuWordNet non-commercial terms +
   versions. Output is for non-commercial use and distribution (not shipped
   as a catalog entry).
6. **Validate:** % headwords with ≥1 equivalent, equivalents-per-sense
   distribution, preview eyeball (same sample→preview→measure habit as the
   kaikki tool).

### Dict A article layout (decided)

One card per headword, senses grouped under Russian POS sections with
numbering restarted per section. Equivalents come first — they are the lookup
answer — with the Russian definition as a subordinate italic line (printed
bilingual dictionaries lead with translations, qualifiers follow). The L1 gloss
is build-debug only and is not displayed. EN synonyms close each sense as
secondary material (they repeat across RU groups that share one EN synset —
accepted):

give
    [p]гл.[/p]
    [m1]1.[/m] [trn]кормить[/trn], [trn]накормить[/trn], …
    [i]давать корм (животным); давать пищу …[/i]
    (syn. feed)
    [*] ex. EN sentence / [trn]RU translation[/trn] (anchored, see below) [/*]
    [m1]2.[/m] [trn]погружаться[/trn], …
    [i]полностью посвятить себя чему-либо …[/i]
    (syn. consecrate, dedicate, devote)

Fallback chain for a missing RU definition (some synsets have none, e.g.
ПОСВЯТИТЬ): RU synset title (always present and itself descriptive, e.g.
ВЫСЛЕДИТЬ (ОТЫСКАТЬ)), lowercased since titles are stored ALL-CAPS — but only
fully-uppercase strings, so natural-case definitions keep their proper nouns.
POS labels are Russian, reusing the repo's own `_RU_POS_LABELS`
(сущ./гл./прил./нареч.), so a future build labels POS exactly like the
monolingual Russian dictionary. EN glosses are never translated by us. Adverb
senses (no `ili`) ship definition + synonyms with no equivalents and count
against coverage.
Within one RU synset the equivalents are ordered common-first by Russian
corpus frequency (exact dupes removed, deterministic ties) — ranking, not
collapsing: dropping a near-duplicate would need semantic judgment
(окунуться vs окунуться с головой — the idiomatic variant is the valuable one).

Examples live in a per-sense collapsible zone (`[*]…[/*]`), exactly like the
kaikki cards — and like the removed learner mode, which tucked extras away so
the equivalents are what a lookup sees first. Rationale: an 11-sense card like
`give` becomes a wall of text otherwise, and the need is *locality*, not
visibility — the zone sits directly under its sense, one tap to reveal, rather
than pooled at the card end. Examples remain the only zone content (no
cross-references exist yet), same rule as the monolingual spec. If on-device
eyeballing shows users expanding every zone, revisit; until then consistency
wins (one interaction to learn across all Aurelex dictionaries).

Examples are fished from Tatoeba by anchoring (composition (b) as ranking):
a pair attaches to a sense when its RU side contains one of that sense's
equivalents. Verified limits, probe 2026-10-22:

- PWN EN examples and RuWordNet RU examples are both unavailable — the bundled
  sqlite schema (16 tables: synset, wn_synset, sense, relations…) has **no
  example tables at all**. Full NLTK PWN would give EN-only examples.
- Anchoring is thin per sense and can misattach: `give` m2 found 2 pairs, and
  inspection shows `Я не разрешал тебе уходить` matched on `уходить` where it
  renders *leave*, not *give*. The obvious cross-check (does another EN word in
  the sentence claim the equivalent?) fails here precisely because of a
  RuWordNet gap — `leave` itself has no `уходить`.
- Mitigation: rarity-weighted anchoring — prefer pairs anchored by distinctive
  equivalents (`посвятить`) over high-frequency verbs (`уйти`) that occur
  everywhere; common concrete senses (`bread`/`хлеб`, 615 anchored) need none.
  Residual mismatch is eyeballed, not solved.
- kaikki EN examples are **not** reused as sense examples: they are English-only
  and qualified against kaikki senses, which do not align with PWN synsets. A
  sense with no anchored Tatoeba pair falls back to an unanchored pair
  (concordance — still bilingual), never to a kaikki example.

Audio is inherited from kaikki, not rebuilt: Dict A headwords are English
lemmas, so the kaikki EN build already resolved and bundled their pronunciation
recordings (`[s]name[/s]` + sibling resource bundle). A Dict A build reuses that
audio stage verbatim (same planner, same cache) rather than inventing a new
one. Coverage inherits kaikki's (~10% of cards vocal, plus whatever the
Lingua Libre additional-source work adds) — a Dict A card is silent exactly
where the monolingual EN card is.

## Dict B: sentence pairs (Tatoeba)

**Inputs:** weekly Saturday exports at `downloads.tatoeba.org/exports/`:
`sentences.csv` (~760 MB, ~219 MB bz2) + `links.csv` (~458 MB, ~150 MB bz2) —
or the on-demand A→B pair export for eng→rus.

1. **Pair table:** join sentences↔links on id, filter eng↔rus. Optional quality
   filters for the probe: `users_sentences.csv` reviews, `sentences_base`
   (original vs translated), audio-availability list.
2. **Headword index:** same headword list as Dict A (so the two compose); a pair
   qualifies when its English side contains the headword (case-insensitive
   word-boundary match, same discipline as the converter's example-qualification).
3. **Selection (decided): dedupe → rank → cap.** One EN sentence ships once —
   there is no reason to provide different translations of the same sentence.
   Group pairs by normalized EN text and keep one RU variant per group: prefer a
   variant whose RU side contains a Dict-A equivalent (sense-anchored — this is
   composition (b) as a *ranking*, not a filter: `time` has zero anchored pairs
   and must still get examples), else the pairing with the shortest EN text.
   Rank survivors anchored-first, shortest-first, and keep N per headword
   (probe: 3; a tunable build parameter). Length is a ranking signal, not a
   filter: a headword whose only pairs exceed the preferred length (probe: 140
   chars) still keeps its best pair rather than shipping nothing. Statistical
   aligners (`fast_align`) are out of scope — unnecessary once selection is decided.
4. **Render:** headword → EN+RU pairs as `[ex]`; no `[trn]` claims except via (b).
5. **Validate:** % headwords with ≥1 pair, pairs-per-headword; attribution
   embedded (CC BY 2.0 FR). Audio skipped in the probe (per-contributor licenses).

## Composition

Dict A first (equivalents are the load-bearing unknown — its coverage % decides
everything), then Dict B selection against the same headwords with Dict-A
equivalents as the ranking signal. Full-run cost is bounded the same way as the
kaikki tool: sample, preview, measure, then decide.

## Exit criteria

| Probe | Viable if | Then |
| --- | --- | --- |
| Dict A core-5000 | coverage clearly above the native ~11% with clean sense grouping | open an OpenSpec change (new capability spec alongside `dictionary-conversion`; the monolingual spec stays untouched) |
| Dict A core-5000 | at or below native coverage, or `ili` links too noisy on eyeball | record the negative result here with numbers; no change opened |
| Dict B | dedupe → rank → cap yields shippable pairs at useful density (probe: yes — 3 kept per headword, 0/50 empty) | fold into the same change as examples |

## Results

2026-10-22, 50-word probe (common nouns/verbs/adjectives; same list for both
dicts so composition is testable). Artifacts in `Temp/opencode/bil/` (not repo
files): `dictA-sample.dsl` + `.preview.html`, `dictB-sample.dsl` + `.preview.html`.

| Probe | Coverage | Notes |
| --- | --- | --- |
| Dict A 50-word probe (bundled EN subset) | 50/50 words resolve; 215 en synsets, **215 linked (100%)**; 1,304 ru lemmas | 100% is a subset artifact — the bundled EN set contains only linked synsets. Sense grouping clean on eyeball; article-shape decisions (L2 defs, RU POS, zoned examples) validated here |
| Dict A core-5000 (full-PWN denominator) | 4,953 distinct core synsets; 4,187 linked (**84.5%**): nouns 84.3%, verbs 88.0%, adjectives 81.5%, satellites 77.1%; 30 keys (0.6%) unresolvable through NLTK (sense-key drift) | **Gate passes** — clearly above native ~11%. Overall `ili` covers 21,138/117,659 EN synsets (~18%); core vocabulary is covered far better than the long tail. Satellite figure verified genuine (table holds `-s` ids; no `-a` aliasing) |
| Dict B (Tatoeba eng→rus) | **831,236 pairs**; 26.8% of eng sentences linked; 0/50 words with zero pairs (476 for `moon` … 32,634 for `know`) | raw counts are unusable directly — the selection funnel (dedupe EN text → one RU variant per text, prefer Dict-A-anchored → length ≤140 → keep 3 in the probe) collapses `know` 32,634 → 19,076 distinct EN → 3 kept (`Let me know.` / `I must know.` / `Let Tom know.`); `time` 13,556 → 3; `moon` 476 → 3. One EN sentence often has several RU variants (real translation variants). Same per-headword-cap pattern as the converter's example qualification |
| Pairs universe and keep-N | 860,950 lexical kaikki EN headwords; 40,210 have ≥1 pair (**4.7%**) | full `--mode pairs --all-kaikki` build: **46,099 cards** (of 884k universe; probe counted a slightly smaller one), 6.01 MB `.dsl.dz`, smoke-verified (`gd_lookup` returns full flat articles, no markup warnings). Default keep **5** (+2.4 MB over k=3: 85,700 → 117,228 pairs) |
| Composition (b) | **21.1%** of word-touching pairs contain a Dict-A equivalent in the RU side | lower bound (lemma-vs-inflected matching). Architecture viable: A gives words, B gives sentences |
| End-to-end sample (7.1) | `give`/`bread`/`dog` → 4 cards, 15/15 synsets linked; `.dsl.dz` + `.dsl.files.zip` (8 audio: archive + 3 Wikimedia fetches) + `.ann`; `verify_bundle` **0 unresolved** | real-reader verified via the host smoke tool: `gd_lookup` returns full articles (11 numbered senses, `dsl_trn` equivalents, `dsl_opt` zones with working expander, `gdau://` audio resolving to bytes); the build also surfaced and fixed two emitter bugs (`[/opt]`→`[/*]`, `[m10]+`→text numbering) |
| Full-build feasibility | EN lemma universe 35,676; Tatoeba acquire+index 55.8 s for 831,236 pairs; 13-word lookup 2.39 s | per-headword regex over all pairs (~35k × 831k) would never finish — the inverted index (exact word-boundary regex still decides) makes the full build the same cost class as a kaikki full build (hours, desktop) |
| Headword universe vs usage | 35,676 lemmas (~24% of PWN's ~148k) but 73.7% of content-word tokens covered (Tatoeba EN, naive stemming, function words excluded) | small headword count, large usage coverage: the linked set skews to core vocabulary (core-5000: 84.5%). The missing long tail is rare words — a source gap, not a pipeline gap |

Dict A rendering fixes needed before any real build (all probe artifacts, not data
problems): POS must come from the synset (probe hardcoded `n.`); RuWordNet
lemmas are ALL-CAPS and need lowercasing (proper nouns excepted); aspectual verb
pairs (ДАВАТЬ/ДАТЬ) both list — keep, it is useful.

Gate status: **passed** 2026-10-22 — core-5000 coverage is 84.5%, clearly above
native ~11%, with clean sense grouping on eyeball. Proceed to builders. Known ceiling from
the schema: `interlingual_index_relation` covers 21,138 EN synsets (~18% of
PWN's 117k) — directionally 2–4x native, same-unknown representativeness caveat.

### Pairs article decisions (from the 2026-10-23 review of the built dictionary)

Measured on the full build: 192 of 46,099 cards (0.4%) had junk headwords —
stray-quote duplicates (`'dog`, `'is`), suffix fragments (`-er`, `-x`), bare
numbers (`007`, `1-800`). General rule, no case list: a headword must start
with a Unicode letter, else no card (reported as ill-shaped skips, alongside
the no-pairs skips). This costs a handful of legitimate clippings (`'cause`,
`'em`) — findable via full-text search anyway.

Pairs are the whole article, so they are **not** collapsed: flat `[ex]`/`[trn]`
lines, the Russian line marked `[trn]` since it is a translation, not an
example. Same `[trn]`-for-RU convention now applies to Dict A sense examples
(the equivalents were already `[trn]`). Verified through the real reader:
`gd_lookup("bread")` returns flat pairs with no zone and no warnings; the same
shape holds for every card by construction.

Case variants with identical bodies (`maduro`/`Maduro`, 5,223 groups) collapse
into one card: the lowercase form wins when it occurs as a whole word anywhere
in the group's own pairs (the card-body heuristic — common nouns surface
lowercase somewhere; mid-sentence, so sentence-initial capitals do not fool
it), otherwise the capitalized form stands (`Sisyphus`, `Sint Maarten`, proper
nouns never occur lowercase). Between several capitalized forms the
alphabetical one wins; pairs are identical either way since matching is
case-insensitive.

Deliberately NOT stripped: leading `a`/`the`. Checked against the snapshot,
`A Special` / `A battery` / `A band` / `A flat` / `A major` / `The Hague` /
`a priori` are all legitimate headwords (special police units, myofibril
bands, tube batteries, musical keys, cities, Latin borrowings) — stripping the
article would corrupt them (`A major` → `major` changes the meaning). `a 1`
is not a kaikki headword at all.

Note: this contradicts the archived `bilingual-dictionary` spec's
"single collapsible zone" requirement for examples-only cards — it needs a
delta in the next change.
