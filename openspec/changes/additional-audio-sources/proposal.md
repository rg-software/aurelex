## Why

The audio in a published dictionary is exactly what the source snapshot's `sounds`
fields link to, and nothing else: `AudioPlan.plan` walks a record's own sounds, so a
recording the snapshot never mentioned can never reach an article. Measured against the
three published dictionaries, that leaves most entries silent — 9.89% of `au_kaikki_en-en`,
4.19% of `au_kaikki_ru-ru`, and 0.08% of `au_kaikki_ja-ja`.

A large corpus of usable recordings sits outside that reach and is systematically
unharvested: Lingua Libre encodes the word it records in the file name
(`LL-Q5287 (jpn)-Higa4-あいだ.wav.ogg`), so a recording can be found *by the word* with no
per-word lookup. Wikimedia Commons holds 109,396 English, 34,359 Russian and 1,055
Japanese files in its Lingua Libre categories, against 9,249, 419 and 0 distinct recordings
respectively in our local 20 GB audio archive — the local archive is a bulk snapshot, and
the recordings our dictionaries use today arrive through the download cache instead. The
gap is therefore not a download problem; it is that nothing has ever asked for a
recording by word.

The corpus converts well once asked. Of the 983 distinct words the Japanese category
records, 697 are readings or headwords the ja dictionary already indexes; of the
archive-resident English recordings, 8,006 name an indexed headword; of the Russian
ones, 244 do. For Japanese alone that is roughly 715 additional recordings — about
0.72% coverage, more than nine times what the dictionary has today.

## What Changes

- **Additional audio sources become a general, per-language capability.** A source is a
  named corpus whose recordings can be enumerated and matched by the word they record.
  The source-language profile declares which sources cover that language and which
  language code the corpus files it under; a run opts in by naming a source.
- **Matching uses the whole card, not just its headword.** Candidates are matched against
  the headword, the card's inflected forms, and its readings. This is what makes a
  kana corpus (Japanese records the reading) and an inflected corpus (Lingua Libre Russian
  is largely inflected forms such as `августа` and `воза`) convert at all, and it does not
  require reading indexing to be enabled.
- **Snapshot audio keeps its slots.** An additional source only fills slots the snapshot
  left empty, so it can add a recording to a silent article but never displace a
  recording the source itself supplied. The existing per-headword limit still bounds the
  total, and audio disabled still means no audio.
- **Acquisition is unchanged and already built.** A matched candidate becomes an ordinary
  wanted name and is located exactly as a snapshot recording is — local cache, audio
  archive, or a fetch through the existing sharded prefetcher, with its 404 learning. The
  source index itself is cached under a fingerprint so a repeated run needs no network.
- **Enabling a source requires writing the bundle.** A dictionary that references new
  recordings cannot reuse an existing bundle, so the two are mutually exclusive and the
  refusal is explicit rather than a later integrity failure.
- **A second source carries its own licence and credit.** Lingua Libre recordings are
  CC BY-SA with per-recording speaker attribution, which the current single-source
  attribution does not model: the about article and the sibling annotation name each
  contributing source and its licence and record where per-recording credit lives.
- **The build reports what each source contributed**, so a run states how many
  recordings came from where.

Lingua Libre is the first source and the reference implementation; the capability is
defined so a second corpus needs a new index and a profile entry, not a new mechanism.
Enabling it for a language is a separate, evidence-based decision — Japanese gains the
most from it relative to what it has, English the most in absolute volume, and Russian
depends on whether matching forms is worth enabling there.

## Capabilities

### New Capabilities

- `additional-audio-sources`: recordings from a source other than the snapshot — how a
  source's index is built and cached, which forms are matched, how candidates are ranked
  against snapshot audio, how they are located and bundled, and how they are attributed.

### Modified Capabilities

- `dictionary-conversion`: "Bounded pronunciation audio" gains that an enabled additional
  source may fill slots the snapshot left empty while the per-headword limit still
  bounds the result; "Provenance and attribution" gains that a dictionary built with
  additional sources names each of them and its licence and records where per-recording
  credit is kept.

`sharded-audio-prefetch` and `audio-bundle-rebuild` are deliberately unchanged: a matched
candidate reaches the cache through the existing list-driven fetch, and the rebuild mode
locates a cached recording by the same match key as any other.

## Impact

- `scripts/kaikki/audio.py` — the candidate lookup becomes source-aware: an index of
  word → recordings is consulted for slots the snapshot did not fill, and a matched
  recording enters planning as an ordinary wanted name.
- `scripts/kaikki/profiles.py` — `LangProfile` declares the sources covering a language,
  the corpus language code, and which forms are matched.
- `scripts/kaikki/` (new module) — the source-index abstraction, the Lingua Libre
  implementation (enumerating a Wikimedia Commons category, parsing the recorded word out
  of the file name), and the cached index with its fingerprint.
- `scripts/kaikki/build.py`, `cli.py`, `kaikki-to-dsl.py` — the opt-in flag, the refusal to
  combine it with `--reuse-bundle`, the attribution text, and the contribution report.
- `scripts/tests/` — tests for word extraction per source, form/reading matching,
  precedence against snapshot audio, index caching, and the mutual exclusion.
- `docs/KAIKKI-CONVERSION.md` — the source option, the per-language decision, the
  attribution, and the measured yield per language; `README.md` — the planned coverage
  note under the catalog table.
- No engine, app, or boundary code is touched; the app gains play controls on entries that
  are currently silent.