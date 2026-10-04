## Context

See proposal.md — Why for the motivation. What shapes the approach:

- `AudioPlan.plan(record)` is the single funnel for audio: the renderer calls it once
  per record (`render.py:479`) and the prefetcher calls it once per record
  (`prefetch.py:93`). It returns final bundle names, mutates `referenced`, and reports
  what it could not resolve in `missing`. Anything that reaches an article goes through
  it, so a source-aware candidate stream lands in one place and both callers inherit it.
- A candidate is accepted only if it is *obtainable*: `available` (the archive's name
  index) contains one of its keys, or a fetch through the cached downloader succeeds.
  An accepted candidate becomes a wanted name with `aliases` (every archive key that could
  satisfy it) and is bundled under the name the article references. That is the whole
  locate path, and it is reusable by a candidate that arrives from anywhere.
- The pipeline already owns the comparison a corpus's own spelling needs:
  `_audio_match_key` is basename, percent-decoded, spaces to underscores, casefolded.
  The archive's own listing is *lower-cased* (`ll-q5287_(jpn)-higa4-あいだ.wav.ogg`),
  which is why the fold exists; a corpus name and a card name therefore compare directly
  once folded.
- `available_audio_keys` builds the archive's name index once and caches it beside the
  archive under an identity header (`_archive_identity`: path, size, mtime, sha256
  sidecar), rebuilding only when that changes. This is the precedent for caching a
  source's index.
- `fetch_list` reads a `name<TAB>url` file and fills a cache with **no snapshot and no
  archive**, and `prefetch-audio --split N` writes such files as disjoint shards. A
  source that can emit that format is therefore fetchable by the existing machinery,
  sharded across machines, with the existing retry, resume and 404 learning.
- `bundle_audio` locates a recording by match key whether it sits in the cache or the
  archive, so it needs no change to serve an additional source's files.
- Language data lives in `LangProfile` / `LANG_PROFILES`, which already carries
  `has_audio`, reading tags and per-language tag sets. A corpus's language identity is
  language data and does not fit there: Lingua Libre files Japanese under `jpn`, Russian
  under `rus`, English under `eng`, while the profiles are `ja`, `ru`, `en`.
- An article's audio is `[s]name[/s]`, markup that also carries the sense-marker icons;
  audio is told apart by extension (`AUDIO_EXTENSIONS`). An additional source's recording
  is emitted with identical markup, so no app, asset or boundary change is involved.

## Goals / Non-Goals

**Goals:**

- One mechanism for any corpus whose recordings name the word they record: a second
  source is a new index plus a profile entry, not a new code path.
- Reuse the locate, extract, cache, shard and 404 machinery unchanged; a matched
  candidate becomes an ordinary wanted name.
- Leave every existing build byte-identical when the option is off, and leave the
  snapshot's own choice of recording untouched when it is on.
- Make the expensive half (thousands of fetches) happen *before* a render, in work that
  can be sharded and resumed.

**Non-Goals:**

- Choosing a *better* recording than the snapshot did, ranking speakers, or scoring
  quality. The corpus's own order plus the existing ogg preference is the whole policy.
- Sources whose recordings cannot be matched by name. They would need a per-word lookup,
  which is not affordable at dictionary scale.
- Changing the per-headword limit, the `missing` reporting contract, or the dead-list
  behaviour.
- Deciding which shipped dictionaries enable this. That is an evidence-based,
  per-dictionary decision made from the build report.
- Any engine, app or boundary change.

## Decisions

**D1 — A source is an index from a normalised form to candidates, built once and cached
under a fingerprint.**
Each source implements: an enumeration of its recordings for one corpus language, and a
word extractor over a recording's name. The product is a lookup table, so plan-time
matching is a dict hit per form rather than a scan per card — 883k cards times 9,249
archive recordings is not affordable, a dict is. The cache follows `available_audio_keys`:
a header line holding the fingerprint, the rows beneath it, written to a `.part` file and
`os.replace`d. The fingerprint covers the source id, the corpus language, what the listing
request asked for, and the index format version. Alternatives: (a) query per word while
rendering — 883k HTTP requests, and it would put the render on the network; (b) list the
corpus inside `plan()` — the same cost repeated per card; (c) no cache — the en listing is
~220 paginated requests and the ru one ~69, and rebuilding them per run is what made this
worth designing rather than scripting.

**D2 — Matching compares folded spellings against a profile-declared set of match
targets; reading indexing is not involved.**
The headword is always a target. A profile may add the card's inflected forms and its
readings. This is what makes the two hard cases convert: Lingua Libre Japanese records the
*reading* (636 of its 697 matchable words are readings, not headwords), and Lingua Libre
Russian is largely inflected forms (`августа`, `воза`, `компромат`). Folding gives case
and separator insensitivity for free — the corpus writes underscores where a card writes a
space. Deliberately decoupled from `--index-readings`: that option changes what a *lookup*
finds, while this changes what a *card* can be given, and coupling them would make the
audio yield depend on an unrelated flag. Alternatives: (a) headwords only — measured
against the local archive this is 98 free recordings for en and 193 for ru against 8,006
and 244 matchable, i.e. the feature would look broken; (b) always match everything — no
per-language control over whether an inflected corpus is appropriate, which is a judgement
about the language, not the corpus.

**D3 — Snapshot audio keeps precedence because the source is a second candidate stream
consulted only after the record's own sounds are exhausted.**
`plan()` scores the record's own sounds, accepts them through the availability/fetch gate,
and stops at `per_word`. The extension appends source candidates afterwards, only while
`len(chosen) < per_word`, through the same gate. Alternatives: (a) merge both streams into
one scored list — the score would then let a corpus recording outrank the snapshot's own,
which the spec forbids and which is the wrong default for a dictionary; (b) plan sources in
a separate pass — two passes over every record, and the prefetcher's per-record call would
have to know about both; (c) plan at render time only — then the prefetcher, which is how a
large audio back-fill actually happens, would never see these candidates and could not
produce the wishlist that makes them fetchable (D7).

**D4 — A source contributes a candidate shaped like a snapshot sound, so the existing
locate path serves it verbatim.**
Lingua Libre gives a Commons file title, from which the download URL and the basename
follow by the same rules the pipeline already applies to `ogg_url`. So a candidate is
`{"audio": <name>, "ogg_url": <url>}` and inherits availability checking, fetching with a
sha256 sidecar, permanent-failure learning into the dead list, `missing` reporting,
`aliases` and `referenced`. Alternatives: a parallel "source bundle" writer — a second
implementation of locate/extract/verify to keep in sync, which the sibling change
`audio-bundle-reference-integrity` shows is exactly where the current defects live.

**D5 — Licence and per-recording credit are captured while the corpus is being listed,
not looked up later.**
The listing request already returns `extmetadata` (artist, licence) for the files it
returns, so the credit is free there and impossible afterwards without re-querying per
recording. Each index row therefore carries the source id, that source's licence, the
recording's credit and its URL. The about article names the contributing sources and their
licences and states where the per-recording credit lives. Alternative: state only the
licence — insufficient for CC BY-SA material, which requires crediting the author of each
recording.

**D6 — The source emits the standard `name<TAB>url` wishlist, so the existing prefetcher
does the fetching.**
This is the cost lever. The English prize is on the order of tens of thousands of
recordings; fetching them inline during a render would take hours and put the render on the
network. A new mode lists the source, intersects it with the snapshot's forms (so the list
never carries a recording no card wants), and writes the same file format
`prefetch-audio --split` and `fetch-list` already consume — after which N machines can take
N shards with the existing politeness, retries and resume, and the render later finds a
warm cache. Alternatives: (a) inline fetching — hours inside a render that is already the
longest step; (b) a bespoke downloader for the corpus — new rate-limit handling, new resume,
new dead-list semantics, all of which already exist and are tested.

**D7 — The index lives beside the other kaikki caches, keyed by source and corpus language,
and is independent of the dump date.**
A corpus listing does not change with a kaikki dump, so the index is built once and reused
across dump dates and shipped to workers with the shard job. That also means the cache
cannot go stale against the snapshot the way a dump-date-keyed artefact would.

**D8 — Enabling a source and `--reuse-bundle` are mutually exclusive, refused while
arguments are validated.**
A reused bundle is verified against the dictionary's references, and a new reference cannot
be satisfied by a bundle that was built without it. Refusing at validation states the
conflict in one line; the alternative is discovering it as an integrity failure at the end
of a long render, or — if verification were relaxed — shipping a dictionary whose bundle
cannot serve a link.

**D9 — Off by default; the profile declares availability, the run opts in.**
A source's availability for a language is language data (the corpus may not cover the
language at all, hence the refusal when a run enables an undeclared source), while the
decision to pay for it is an operator decision with visible consequences — bundle size,
digest, and hours of render. Enabling it from the profile alone would silently change
every published artifact for every operator. The report states each source's contribution,
so the decision for the next language is made from a measurement rather than an estimate.

## Risks / Trade-offs

- [Listing a large corpus costs hundreds of paginated API requests, and Wikimedia
  rate-limits] → the index is cached under a fingerprint (D1) and built once per language
  (D7); pagination resumes from where it stopped; requests are spaced and retried with
  backoff on 429, as the other Wikimedia access in this pipeline already does.
- [Bundle size grows where a corpus is large — English most of all] → bounded by
  precedence and the per-headword limit (D3), opt-in (D9), and the report states the
  contribution count before the operator republishes. The English decision can wait for a
  measurement on a cheaper dictionary.
- [Crediting thousands of recordings individually is impractical inside a dictionary]
  → the per-recording credit is held in the index and the about article states where it
  lives (D5), which is how a bundled derivative of CC BY-SA material is credited in
  practice; whether a sidecar should ship beside the bundle is an implementation choice
  under this spec, to settle on the Japanese pilot.
- [A recording of an inflected form attached to a base-form card may not be the reading a
  reader expects] → only profiles that declare form matching pay this, so it is a
  per-language judgement, and recording order within a card is the corpus's.
- [Folding can make two distinct recordings collide] → `_final_name`'s existing
  digest-suffixed disambiguation applies unchanged.
- [The bulk archive holds *some* corpus recordings (9,249 English, 419 Russian, none
  Japanese), so the same candidate may be served from the archive rather than fetched]
  → the availability gate already decides per candidate, and the archive's lower-cased
  spelling is exactly what the fold handles.

## Migration Plan

1. Land the abstraction, the Lingua Libre index, the profile declaration and the
   opt-in flag with the option **off**, plus reporting. No published artifact changes and
   no existing test result moves.
2. Pilot on the cheapest dictionary: a Japanese sample build with the source enabled,
   checking that the reported contribution is in the range the offline estimate predicted
   (~715 new recordings) and that every new reference resolves to a bundled file.
3. Enable for Japanese and publish; take the per-language decision for Russian and English
   from their own reports rather than from this pilot.
4. Leave the bulk prefetch path (`prefetch-audio --split`, `fetch-list`) unchanged
   throughout — the source only contributes a wishlist in the format they already read.

Rollback is turning the option off; the flag is the whole surface. No data migration, and
until a source is enabled for a shipped dictionary no published digest changes.

## Open Questions

- Whether English's volume justifies re-rendering an 883,403-entry dictionary when the
  fetch side becomes cheap but the render does not. Answerable from the Japanese pilot's
  timings; it affects only whether English is enabled, not the specs or the mechanism.
- Whether `--index-readings` should also imply "match readings". Today the two are
  independent by design (D2); making the flag imply both would be a CLI-ergonomics choice,
  not a behaviour the specs require.
- Whether the per-recording credit should ship as a sidecar beside the bundle. The spec
  requires only that the about article state where the credit lives, so either answer
  satisfies it; settle it on the pilot, where the credit file's real size is visible.