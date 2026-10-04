## 1. Source abstraction and the index cache

- [ ] 1.1 Add a source abstraction in `scripts/kaikki/`: a source has an id, a corpus
      language code, an enumeration of its recordings, and a word extractor over a
      recording's name; the enumeration yields a candidate shaped like a snapshot sound
      (`audio` name plus `ogg_url`) together with its licence and per-recording credit.
- [ ] 1.2 Fold both sides of a match with the pipeline's existing normaliser
      (`_audio_match_key`), so corpus spellings, the archive's lower-cased spelling and a
      card's spelling compare equal regardless of case or separator.
- [ ] 1.3 Build the index as a lookup table from a normalised form to candidates, built once
      per source and corpus language.
- [ ] 1.4 Cache the index under a fingerprint header (source id, corpus language, listing
      request, index format version), reusing the write-to-`.part`-then-`os.replace` pattern
      of `available_audio_keys`; rebuild when the fingerprint differs.
- [ ] 1.5 Place the cache beside the other kaikki caches, keyed by source and corpus
      language, independent of the snapshot dump date.

## 2. The Lingua Libre source

- [ ] 2.1 Enumerate a corpus language's recordings from its Wikimedia Commons category,
      paginating with `cmcontinue` and carrying the `File:` namespace prefix into the
      download URL.
- [ ] 2.2 Space requests and retry `429` with backoff, as the pipeline's other Wikimedia
      access does; report a listing that could not complete rather than caching a partial
      index as if it were whole.
- [ ] 2.3 Extract the recorded word from `LL-Q<id> (<lang>)-<speaker>-<word>.<ext>`, split
      speaker from word on the first hyphen, and percent-decode.
- [ ] 2.4 Collapse a recording's transcodes to one entry, preferring `.ogg`, so an
      `.ogg`/`.mp3` pair does not consume two slots or two wishlist lines.
- [ ] 2.5 Capture `extmetadata` (artist, licence) per recording as its credit, and declare
      the source's licence and where its per-recording credit lives.
- [ ] 2.6 Refuse a recording whose name yields no word instead of indexing it.

## 3. Language profile declaration

- [ ] 3.1 Extend `LangProfile` with the additional sources covering the language, the
      corpus language code each uses, and which match targets apply (headword always,
      forms and/or readings).
- [ ] 3.2 Declare the Japanese profile with the `jpn` corpus, readings and headwords as
      match targets; leave the Russian and English declarations to their own measured
      decisions (Russian forms, English headwords), with the fields present and empty.

## 4. Plan-time integration

- [ ] 4.1 Load the enabled sources' indexes before the render loop and pass them to
      `AudioPlan`.
- [ ] 4.2 After a record's own sounds are exhausted, look the card's declared match targets
      up in each enabled source's index and offer the candidates that the card's language
      profile allows.
- [ ] 4.3 Push those candidates through the existing availability and fetch gate, so an
      additional-source recording is served from the archive or the cache exactly as a
      snapshot recording is, and lands in `referenced`, `aliases` and `missing` like any
      other.
- [ ] 4.4 Stop filling at the per-headword limit and never displace a recording the
      snapshot supplied; make a per-word limit of zero suppress the sources too.
- [ ] 4.5 Leave `AudioPlan` unchanged in behaviour when no source is enabled, including
      its `referenced`, `missing` and dead-list handling.

## 5. The wishlist the prefetcher can consume

- [ ] 5.1 Add a mode that writes a `name<TAB>url` wishlist for an enabled source,
      intersected with the snapshot's headwords, forms and readings so no recording no card
      wants is listed.
- [ ] 5.2 Route that wishlist through the existing `prefetch-audio --split N` sharding and
      `fetch-list` worker path without changes to either.
- [ ] 5.3 Verify a sharded back-fill of a source's wishlist reaches a warm cache, and that a
      build afterwards needs no network for those recordings.

## 6. Attribution and reporting

- [ ] 6.1 Extend the attribution description with every contributing source and its licence,
      and state where the credit for an individual recording is recorded.
- [ ] 6.2 Show the same description in the about article and the sibling annotation, and
      keep a snapshot-only dictionary's description exactly as it is today.
- [ ] 6.3 Report, per enabled source, how many recordings it contributed and how many cards
      gained audio, and say so when a source contributed nothing and when none was enabled.

## 7. CLI wiring

- [ ] 7.1 Add the opt-in option to `kaikki-to-dsl.py` and thread it through `cli.py` to
      `build()`; default off.
- [ ] 7.2 Refuse, while validating arguments, a run that both enables a source and reuses
      an existing bundle, with a message explaining that new recordings cannot be added to
      a reused bundle.
- [ ] 7.3 Refuse a run that enables a source the language profile does not declare, naming
      the source and the language, and exit non-zero without producing a dictionary.

## 8. Tests

- [ ] 8.1 Word extraction from corpus names: a single word, a hyphenated name, a
      multi-word name, a reading, an inflected form, percent-encoded characters, a name with
      no recoverable word, and a recording with no word at all.
- [ ] 8.2 Matching: headword, reading and inflected-form matches; case and separator
      insensitivity; a form the profile does not match; a recording no card wants.
- [ ] 8.3 Precedence: a card already at the limit gains nothing, a card with a free slot
      keeps its snapshot recording, the limit bounds the combined total, and a limit of zero
      yields nothing.
- [ ] 8.4 Locating: an archive-resident candidate, a cache-resident candidate, a candidate
      fetched on demand, and a candidate that resolves nowhere freeing its slot and being
      reported.
- [ ] 8.5 Index caching: a second run reuses the index without a listing request, a changed
      fingerprint rebuilds it, and an incomplete listing is not cached as whole.
- [ ] 8.6 Attribution and reporting: two contributing sources named with their licences, a
      snapshot-only dictionary unchanged, per-source contribution counts, and a source that
      matched nothing reported as such.
- [ ] 8.7 CLI: the default run enables no source; enabling with `--reuse-bundle` and
      enabling an undeclared source both fail non-zero with their message.

## 9. Documentation and the pilot

- [ ] 9.1 Document the option, the per-language declaration, the attribution, the wishlist
      path and the measured yield per language in `docs/KAIKKI-CONVERSION.md`, alongside the
      measured audio-coverage section.
- [ ] 9.2 Note the planned additional sources under the catalog table in `README.md`.
- [ ] 9.3 Pilot: a Japanese sample build with the source enabled, confirming the reported
      contribution against the offline estimate (~715 new recordings) and that every new
      reference resolves to a bundled file.
- [ ] 9.4 Record the pilot's timings, so the English decision (open question in
      `design.md`) can be made from a measurement.