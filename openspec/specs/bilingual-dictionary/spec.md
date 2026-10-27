# bilingual-dictionary Specification

## Purpose

Builds offline translation dictionaries from sense-aligned WordNet-family
equivalents and Tatoeba example sentences, packaged for the existing folder
import.

## Requirements

### Requirement: Sense-aligned equivalent resolution

The system SHALL resolve Russian equivalents through Princeton WordNet synsets
bridged to RuWordNet synsets via their `ili` links, so equivalents inherit the
synset's sense grouping with no fuzzy sense-key matching. Senses with no `ili`
link (including all adverb senses) SHALL resolve without equivalents and SHALL be
counted in the build report. A sense with neither equivalents nor a definition
SHALL be omitted from the article.

#### Scenario: Linked sense resolves

- **WHEN** an English synset has one or more `ili`-linked RuWordNet synsets
- **THEN** every member lemma of each linked synset becomes an equivalent of
  that sense, grouped under its own RU synset

#### Scenario: Unlinked sense is counted

- **WHEN** an English synset has no `ili` link
- **THEN** the sense resolves with no equivalents and the run counts it as uncovered

#### Scenario: Content-free sense is omitted

- **WHEN** a sense carries neither equivalents nor a definition
- **THEN** no numbered section is rendered for it, though it stays counted
  in coverage

### Requirement: Russian definitions

Each sense SHALL carry its definition in Russian, taken from its RU synset. A
synset with no definition SHALL fall back to its synset title,
sentence-cased. The system SHALL NOT translate English glosses into Russian;
the English gloss is NOT displayed.

#### Scenario: RU definition shown

- **WHEN** a sense's RU synset carries a definition
- **THEN** the article shows that definition as subordinate italic text under
  the equivalents

#### Scenario: Empty definition falls back to title

- **WHEN** a sense's RU synset has no definition
- **THEN** the article shows the sentence-cased synset title, so proper-noun
  titles survive as titles

### Requirement: Translation article layout

Each headword SHALL be one article grouping its senses under the target
language's part-of-speech labels (Russian `сущ./гл./прил./нареч.` for *-ru
targets, Japanese `名詞/動詞/形容詞/副詞` etc. for *-ja), numbered per part of
speech (a lone sense in a section carries no counter). Each sense SHALL lead
with its numbered `[m1]` marker followed by its `[trn]` equivalents (bounded
per sense by the stated limit, ordered common-first by target-language
corpus frequency), then its definition as subordinate italic text, then at
most one anchored example pair, then source-language synonyms of the source
synset. The source-language gloss SHALL NOT be displayed. A headword with
no resolvable senses at all SHALL be omitted from the output and counted.

#### Scenario: Senses are numbered per part of speech

- **WHEN** a card has several senses under one part of speech
- **THEN** they are numbered in sequence, restarting at each part of speech

#### Scenario: Equivalents lead, definition follows

- **WHEN** a sense is rendered
- **THEN** its numbered marker and equivalents come first, the target
  definition follows as subordinate text, then the example pair, then
  synonyms, and no source-language gloss is shown

#### Scenario: Lone sense has no counter

- **WHEN** a part-of-speech section holds exactly one sense
- **THEN** no number marker is rendered for it

#### Scenario: Empty headword is omitted

- **WHEN** a headword resolves to no senses at all
- **THEN** no card is emitted for it and the run counts it as skipped

#### Scenario: Japanese-target POS labels

- **WHEN** a card targets Japanese
- **THEN** section labels are the Japanese profile's labels, matching the
  monolingual Japanese dictionary

### Requirement: Japanese WordNet equivalent resolution

The system SHALL resolve Japanese equivalents through Japanese WordNet
synsets sharing Princeton WordNet IDs, so each English synset maps to its
Japanese member lemmas with no fuzzy matching. Unlinked senses SHALL resolve
with no equivalents and count against coverage.

#### Scenario: Linked EN synset resolves to Japanese

- **WHEN** an English synset has a Japanese WordNet entry with the same PWN ID
- **THEN** every Japanese member lemma becomes an equivalent of that sense

#### Scenario: Unlinked sense is counted

- **WHEN** an English synset has no Japanese WordNet entry
- **THEN** the sense resolves with no equivalents and the run counts it as uncovered

#### Scenario: Content-free sense is omitted

- **WHEN** a sense carries neither equivalents nor a definition
- **THEN** no numbered section is rendered for it, though it stays counted
  in coverage

### Requirement: Pivot equivalent resolution for Japanese-Russian

The system SHALL resolve Ja↔Ru pairs through a PWN-ID pivot joining Japanese
WordNet to RuWordNet `ili` links. Each pivot ID hit SHALL become one card sense
with target-language member lemmas as equivalents. Synsets with no pivot hit
SHALL resolve unlinked.

#### Scenario: Ja headword resolves to Russian through the pivot

- **WHEN** a Japanese synset shares a PWN ID with an `ili`-linked RuWordNet synset
- **THEN** each linked RU synset is one sense with its member lemmas as equivalents

#### Scenario: Ru headword resolves to Japanese through the pivot

- **WHEN** a Russian synset's `ili` target has a Japanese WordNet entry with the same PWN ID
- **THEN** each Japanese entry is one sense with its member lemmas as equivalents

#### Scenario: Pivot miss ships synonyms only

- **WHEN** a source synset has no pivot counterpart
- **THEN** the sense resolves with synonyms but no equivalents and counts as unlinked

### Requirement: Japanese definitions

Each sense with a Japanese side SHALL carry its definition in Japanese from
Japanese WordNet. JaWN exposes no synset titles, so a sense with no
definition SHALL show no definition line. The system SHALL NOT
machine-translate glosses; the non-target gloss is NOT displayed.

#### Scenario: JaWN definition shown

- **WHEN** a sense's Japanese synset carries a definition
- **THEN** the article shows that definition as subordinate italic text under the equivalents

#### Scenario: Empty definition shows no line

- **WHEN** a Japanese synset has no definition
- **THEN** the sense carries no definition line, but its equivalents still render

### Requirement: Japanese example matching

Example matching against Japanese text SHALL use substring matching with no
word-boundary assumption, the same discipline as the monolingual converter.
The single-character bar does not apply to Japanese: a single kanji is a
complete word (犬, 水, 本), unlike a one-letter English token.

#### Scenario: Japanese headword matches inside a clause

- **WHEN** a Japanese example contains the headword mid-clause without spaces
- **THEN** the example qualifies and the headword is located inside the clause

#### Scenario: Single-kanji headword matches

- **WHEN** the headword is a single kanji
- **THEN** pairs containing it as a substring match it

#### Scenario: Anchored Japanese pair preferred

- **WHEN** candidate pairs exist with and without a sense equivalent in the Japanese side
- **THEN** the anchored pair is kept, else the shortest pair ships as concordance fallback

### Requirement: Japanese audio and transcription reuse

Japanese headwords SHALL reuse the kaikki Japanese build's audio stage
verbatim — same planner, cache, `[s]` references and sibling bundle.
Transcription SHALL come from the source-language kaikki snapshot, with no
transcription line when the snapshot carries none. A headword silent in its
monolingual build SHALL be silent here.

#### Scenario: Shared JA headword shares audio

- **WHEN** a headword carries recordings in the kaikki JA build
- **THEN** the bilingual card references the same recordings from its own sibling bundle

#### Scenario: Transcription follows the source snapshot

- **WHEN** the source-language kaikki snapshot holds a transcription for the headword
- **THEN** the card shows it as a `[t]` line under the headword, whether or not audio exists

### Requirement: Japanese readings line

Each Japanese-source card SHALL show the headword's readings (kana
transcriptions the source records as transliteration forms, grouped by the
profile's marks) as a subordinate comment line under the transcription,
mirroring the monolingual Japanese card. Across the headword's records the
most common line wins, first-seen breaking ties. A headword with no reading
record carries no line.

#### Scenario: Readings shown under the headword

- **WHEN** the kaikki JA snapshot records readings for the headword
- **THEN** the card shows them grouped by mark (e.g. `音: ケン　訓: いぬ`) as a comment line

#### Scenario: No readings, no line

- **WHEN** no kaikki JA record for the headword carries a reading
- **THEN** the card carries no readings line (and no placeholder)

### Requirement: Opt-in reading indexing

With reading indexing enabled (Japanese sources only), each card SHALL
additionally be indexed under its hiragana reading headwords: the same
article under each reading, opening with the primary headword as its title so
an alias lookup says which word it defines. A reading that collides with a
real headword (or an earlier alias) stays with the first card; aliases never
steal names. With the option off, no alias keys are emitted; non-Japanese
sources are unaffected either way.

#### Scenario: Reading alias opens with the primary headword

- **WHEN** reading indexing is enabled and a headword has a kana reading
- **THEN** the dictionary contains the same article under the reading, titled with the primary headword

#### Scenario: Collision keeps the real card

- **WHEN** a reading equals an existing headword
- **THEN** no alias is emitted for it

### Requirement: Japanese frequency ranking

Equivalent ordering for Japanese-target senses SHALL rank common-first using
Japanese token frequencies from the acquired Tatoeba Japanese side, with
deterministic shorter-first then alphabetical ties. Ranking SHALL NOT drop
equivalents.

#### Scenario: Common Japanese equivalent leads

- **WHEN** a sense has several Japanese equivalents with different corpus frequencies
- **THEN** the most frequent leads and the order is deterministic for pinned inputs

### Requirement: Per-sense example selection

Each sense SHALL carry at most one example pair, selected by dedupe → rank →
cap: pairs group by normalized source text with one target variant kept per
group; ranking prefers pairs whose target side contains one of the sense's
equivalents, then shorter source text. Length is a ranking signal, not a
filter. A sense with no anchored pair SHALL fall back to an unanchored pair,
except a pair already shown under an earlier sense of the same card SHALL NOT
be reused: a sense whose only candidates are all used SHALL carry no example;
kaikki source-language-only examples SHALL NOT be used. Single-character
headwords SHALL match no pairs at all (Japanese single kanji exempt): a
one-letter token in running text is overwhelmingly the article, not the
headword.

#### Scenario: One variant per sentence

- **WHEN** several target translations link to the same source sentence
- **THEN** at most one is kept for a headword

#### Scenario: Anchored pair preferred

- **WHEN** candidate pairs exist both with and without a sense equivalent in
  the target side
- **THEN** the anchored pair is kept

#### Scenario: Long-only sense still ships an example

- **WHEN** a sense's only pairs exceed the preferred length
- **THEN** the best-ranked pair is still kept

#### Scenario: Anchor-less sense falls back

- **WHEN** a sense has pairs but none contains a sense equivalent
- **THEN** the shortest pair is kept as a concordance example

#### Scenario: Used pair is not repeated

- **WHEN** a candidate pair shares its source sentence or translation with a
  pair already shown under an earlier sense of the same card
- **THEN** it is skipped; the next-best unused anchor or the
  next-shortest unused fallback pair is kept, or no example when all are
  used

#### Scenario: Fallback never steals a later sense's anchor

- **WHEN** an anchor-less sense precedes a sense whose equivalent a pair
  contains
- **THEN** that anchored pair stays reserved for its sense and the fallback
  draws from the remaining pairs

#### Scenario: Single-character headword ships no examples

- **WHEN** an English or Russian headword is one character long (e.g. "A" = ampere; the bar does not apply to Japanese single kanji)
- **THEN** no pairs match it and its senses carry no examples, though the
  card itself with equivalents is still emitted

### Requirement: Example placement

Each sense's example pair SHALL render inside a per-sense collapsible zone
directly beneath that sense, and examples SHALL be the only zone content.

#### Scenario: Example sits with its sense

- **WHEN** a sense has a selected example pair
- **THEN** the pair appears in a collapsed zone under that sense, not pooled
  at the card

#### Scenario: No example leaves no zone

- **WHEN** a sense has no selected example pair
- **THEN** no zone is rendered for that sense

### Requirement: Inherited pronunciation audio

The system SHALL reuse the kaikki source-language build's audio stage
verbatim for its headwords — same planner, same cache, same `[s]` references
and sibling resource bundle. A headword silent in the kaikki source build
SHALL be silent here.

#### Scenario: Shared headword shares audio

- **WHEN** a headword carries recordings in the kaikki source build
- **THEN** the bilingual article references the same recordings from its own
  sibling bundle

### Requirement: Import-ready deterministic packaging

The output SHALL be a dictzip `.dsl.dz` plus a sibling resource bundle that the
existing folder import resolves, byte-identical across rebuilds from the same
inputs. The output SHALL introduce no app, engine, or boundary change. The
`#INDEX_LANGUAGE` / `#CONTENTS_LANGUAGE` headers SHALL name the build
direction's source and target languages.

#### Scenario: Existing import consumes the output

- **WHEN** the produced pair is placed in an import folder
- **THEN** the app indexes and renders it with no code change

#### Scenario: Deterministic rebuild

- **WHEN** the tool runs twice on the same inputs
- **THEN** the two outputs are byte-identical

#### Scenario: Headers name the direction languages

- **WHEN** a dictionary is built in either direction
- **THEN** `#INDEX_LANGUAGE` names the source language and
  `#CONTENTS_LANGUAGE` names the target language, so the app classifies
  the dictionary under the correct pair

### Requirement: Reverse equivalent resolution

The system SHALL resolve Russian headwords through RuWordNet synsets
bridged to Princeton WordNet via `ili`: each linked EN synset becomes one
card sense with the EN member lemmas as equivalents (verbatim,
underscores rendered as spaces); fellow RU lemmas of the source synset
become the sense synonyms. A RU synset with no `ili` link SHALL resolve
unlinked: synonyms only, no equivalents, counted against coverage. A sense
with neither equivalents nor a definition SHALL be omitted from the
article.

#### Scenario: RU headword resolves through ili

- **WHEN** a Russian headword's synset links to EN synsets
- **THEN** each linked EN synset is one sense with its EN lemmas as
  equivalents and the RU synset's other lemmas as synonyms

#### Scenario: Unlinked RU synset ships synonyms only

- **WHEN** a Russian headword's synset has no `ili` link
- **THEN** the sense resolves with synonyms but no equivalents and counts as
  unlinked

#### Scenario: Content-free reverse sense is omitted

- **WHEN** a reverse sense carries neither equivalents nor a definition
- **THEN** no numbered section is rendered for it, though it stays counted
  in coverage

### Requirement: English definitions

Each reverse sense SHALL carry its definition in English, taken verbatim
from the linked PWN synset gloss. The system SHALL NOT translate or
re-case it.

#### Scenario: PWN gloss shown verbatim

- **WHEN** a linked EN synset carries a gloss
- **THEN** the article shows that gloss unchanged as subordinate text under
  the equivalents

### Requirement: Reverse article layout

Each Russian headword SHALL be one article grouping its senses under
English part-of-speech labels (`noun/verb/adj/adv`), numbered per part of
speech (a lone sense in a section carries no counter). Each sense SHALL
lead with its numbered `[m1]` marker followed by its `[trn]` equivalents,
then its English definition as subordinate italic text, then at most one
anchored example pair, then Russian synonyms of the source synset. A
headword with no resolvable senses at all SHALL be omitted and counted.

#### Scenario: Target-language POS labels

- **WHEN** a reverse card groups senses by part of speech
- **THEN** the section labels are English, matching the reader's language

#### Scenario: Lone reverse sense has no counter

- **WHEN** a part-of-speech section holds exactly one sense
- **THEN** no number marker is rendered for it

### Requirement: Reverse example selection

Each reverse sense SHALL carry at most one example pair from the flipped
corpus view (Russian source line, English target line), selected by
dedupe → rank → cap: the pair is kept when its English side contains one
of the sense's EN equivalents as a whole word, else the shortest pair
ships as a concordance fallback, except a pair already shown under an
earlier sense of the same card SHALL NOT be reused (no example when all
are used). English frequency ranks; length ranks,
never filters. Single-character headwords match no pairs (Japanese single
kanji exempt).

#### Scenario: EN-anchored pair preferred

- **WHEN** candidate pairs exist both with and without a sense equivalent
  in the English side
- **THEN** the anchored pair is kept

#### Scenario: Anchor-less reverse sense falls back

- **WHEN** a reverse sense has pairs but none contains a sense equivalent
- **THEN** the shortest pair is kept as a concordance example

#### Scenario: Used pair is not repeated

- **WHEN** a candidate pair shares its source sentence or translation with a
  pair already shown under an earlier sense of the same card
- **THEN** it is skipped; the next-best unused anchor or the
  next-shortest unused fallback pair is kept, or no example when all are
  used

#### Scenario: Fallback never steals a later sense's anchor

- **WHEN** an anchor-less sense precedes a sense whose equivalent a pair
  contains
- **THEN** that anchored pair stays reserved for its sense and the fallback
  draws from the remaining pairs

### Requirement: Reverse pronunciation audio

The system SHALL reuse the kaikki Russian build's audio stage verbatim for
reverse headwords — same planner, same cache, same `[s]` references and
sibling resource bundle. A headword silent in the kaikki RU build SHALL be
silent here.

#### Scenario: Shared RU headword shares audio

- **WHEN** a headword carries recordings in the kaikki RU build
- **THEN** the reverse card references the same recordings and the bundle
  carries them

### Requirement: Headword pronunciation

Each translation card SHALL show the headword's pronunciation transcription
as a `[t]` line directly under the headword, whenever the source-language
kaikki snapshot holds one for that headword. The transcription is the most
common value across the headword's kaikki records (first-seen wins ties),
picked with the kaikki notation discipline (IPA unlabeled, other notations
labeled, mismatched-notation sounds skipped). The line is present whether
or not the card carries audio recordings.

#### Scenario: Transcription under the headword

- **WHEN** the kaikki snapshot holds a transcription for the headword
- **THEN** the article shows it as a `[t]` line between the headword and
  the rest of the card

#### Scenario: No transcription, no line

- **WHEN** no kaikki record for the headword carries a transcription
- **THEN** the card carries no `[t]` line (and no placeholder)

#### Scenario: Disagreement collapses to most common

- **WHEN** the headword's records carry different transcriptions
- **THEN** the article shows the most common one, first-seen winning ties

### Requirement: Sample and preview output

The system SHALL provide a sample mode emitting a bounded headword subset and a
preview rendering the sample's articles in human-readable form, deterministic
for the same inputs.

#### Scenario: Sample is reproducible

- **WHEN** the tool runs twice with the same sample inputs
- **THEN** the two samples contain the same headwords

### Requirement: Examples-only cards

The system SHALL support cards with no senses: a headword followed by up to
a stated number of example pairs rendered flat — no collapsible zone, since
the pairs are the whole article — with each source-language line marked
`[ex]` and each target-language line marked `[trn]`, for the
sentence-example dictionary. Sense requirements do not apply to such cards.
The build direction is a parameter (English→Russian, Russian→English,
English→Japanese, Japanese→English, Japanese→Russian, or Russian→Japanese).

#### Scenario: Pairs-only card renders

- **WHEN** a headword has selected pairs but no equivalents
- **THEN** the card shows the pairs as flat `[ex]`/`[trn]` lines with no sense
  numbering and no definition lines

#### Scenario: Reversed direction renders

- **WHEN** the build direction is Russian→English
- **THEN** the Russian line of each pair is marked `[ex]` and the English
  line is marked `[trn]`

#### Scenario: Japanese direction renders

- **WHEN** the build direction targets or sources Japanese
- **THEN** the Japanese line is marked `[ex]` on a Japanese-source card and
  `[trn]` on a Japanese-target card, and the card imports with no code
  change

### Requirement: Translation headword eligibility

A translation-dictionary headword MUST start with a Unicode letter, except
Japanese: native spellings routinely start with a digit and are kept as
long as they contain kana or kanji. Anything else (bare numbers, stray
punctuation) is dropped before resolution and counted, never resolved and
never cached.

#### Scenario: Numeric headword dropped

- **WHEN** a candidate headword starts with a non-letter (bare number, stray quote)
- **THEN** no card is emitted for it and the run counts it as ill-shaped

#### Scenario: Digit-initial Japanese word kept

- **WHEN** a Japanese candidate starts with a digit but contains kana or kanji
- **THEN** it is kept as a headword

### Requirement: Pairs headword eligibility

A pairs-dictionary headword MUST start with a Unicode letter, except
Japanese: native spellings routinely start with a digit and are kept as
long as they contain kana or kanji; anything else
(stray quotes, suffix fragments, bare numbers) is dropped and counted.
The candidate universe is the source-language kaikki snapshot. Headwords
differing only in case merge into one card: the lowercase form wins when it
occurs as a whole word in the card's own pairs, otherwise the capitalized
form stands. Headwords with no pairs are omitted and counted.

#### Scenario: Junk headword dropped

- **WHEN** a candidate headword starts with a non-letter
- **THEN** no card is emitted for it and the run counts it as ill-shaped

#### Scenario: Digit-initial Japanese word kept

- **WHEN** a Japanese candidate starts with a digit but contains kana or kanji
- **THEN** it is kept as a headword

#### Scenario: Case variants merge

- **WHEN** several candidate headwords differ only in case
- **THEN** one card is emitted, named for the lowercase form when the pairs
  spell it lowercase and for the capitalized form otherwise

### Requirement: Provenance and licensing

Every produced dictionary SHALL embed attribution, license terms, and pinned
versions for every source it was actually built from: equivalents name
Princeton WordNet plus the thesaurus used (RuWordNet non-commercial terms
and/or Japanese WordNet with its site link-back); examples name Tatoeba CC
BY; audio names the kaikki snapshot. This lands in the dictionary metadata,
an about article, and a sibling annotation file. The about article SHALL
state the output is for non-commercial use and distribution only when a
non-commercial thesaurus was used. The attribution SHALL name the build
direction.

#### Scenario: Attribution is embedded

- **WHEN** a dictionary is produced
- **THEN** its metadata, about article, and annotation name each used source,
  its license, and its pinned version

#### Scenario: Reversed dictionary names its direction

- **WHEN** the build direction is Russian→English
- **THEN** the about article and annotation describe a Russian-English
  dictionary built from Tatoeba rus-eng pairs

#### Scenario: Reversed translation names its direction

- **WHEN** the build is a Russian→English translation dictionary
- **THEN** the about article and annotation describe a Russian-English
  translation dictionary and name the same pinned sources

#### Scenario: Japanese dictionary names its sources and direction

- **WHEN** the build is an En→Ja, Ja→En, Ja→Ru, or Ru→Ja dictionary
- **THEN** the about article and annotation describe that direction, name
  Japanese WordNet (with version and link-back) alongside any other used
  thesaurus, and state the non-commercial term only when RuWordNet
  contributed
