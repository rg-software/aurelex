# bilingual-dictionary Specification

## Purpose

Builds offline En→Ru translation dictionaries from sense-aligned WordNet-family
equivalents and Tatoeba example sentences, packaged for the existing folder import.

## Requirements

### Requirement: Sense-aligned equivalent resolution

The system SHALL resolve Russian equivalents through Princeton WordNet synsets
bridged to RuWordNet synsets via their `ili` links, so equivalents inherit the
synset's sense grouping with no fuzzy sense-key matching. Senses with no `ili`
link (including all adverb senses) SHALL ship without equivalents and SHALL be
counted in the build report.

#### Scenario: Linked sense resolves

- **WHEN** an English synset has one or more `ili`-linked RuWordNet synsets
- **THEN** every member lemma of each linked synset becomes an equivalent of
  that sense, grouped under its own RU synset

#### Scenario: Unlinked sense is counted

- **WHEN** an English synset has no `ili` link
- **THEN** the sense ships with no equivalents and the run counts it as uncovered

### Requirement: Russian definitions

Each sense SHALL carry its definition in Russian, taken from its RU synset. A
synset with no definition SHALL fall back to its synset title, lowercased. The
system SHALL NOT translate English glosses into Russian; the English gloss is
kept only as build-debug metadata and never rendered.

#### Scenario: RU definition shown

- **WHEN** a sense's RU synset carries a definition
- **THEN** the article shows that definition as the sense heading

#### Scenario: Empty definition falls back to title

- **WHEN** a sense's RU synset has no definition
- **THEN** the article shows the lowercased synset title as the sense heading

### Requirement: Translation article layout

Each headword SHALL be one article grouping its senses under Russian part-of-speech
labels (сущ./гл./прил./нареч.), numbered per part of speech (a lone sense in a section
carries no counter). Each sense SHALL lead with its numbered `[m1]` marker
followed by its `[trn]` equivalents (bounded per sense by the stated limit,
ordered common-first by Russian corpus frequency), then its Russian definition
as subordinate italic text, then at most one anchored example pair, then
English synonyms of the source synset. The English gloss SHALL NOT be
displayed. A headword with no resolvable senses at all SHALL be omitted from
the output and counted.

#### Scenario: Senses are numbered per part of speech

- **WHEN** a card has several senses under one part of speech
- **THEN** they are numbered in sequence, restarting at each part of speech

#### Scenario: Equivalents lead, definition follows

- **WHEN** a sense is rendered
- **THEN** its numbered marker and equivalents come first, the Russian
  definition follows as subordinate text, then the example pair, then
  synonyms, and no English gloss is shown

#### Scenario: Lone sense has no counter

- **WHEN** a part-of-speech section holds exactly one sense
- **THEN** no number marker is rendered for it

#### Scenario: Empty headword is omitted

- **WHEN** a headword resolves to no senses at all
- **THEN** no card is emitted for it and the run counts it as skipped

### Requirement: Per-sense example selection

Each sense SHALL carry at most one example pair, selected by dedupe → rank →
cap: pairs group by normalized English text with one Russian variant kept per
group; ranking prefers pairs whose Russian side contains one of the sense's
equivalents, then shorter English text. Length is a ranking signal, not a
filter. A sense with no anchored pair SHALL fall back to an unanchored pair;
kaikki English-only examples SHALL NOT be used. Single-character headwords
SHALL match no pairs at all: a one-letter token in running English text is
overwhelmingly the article, not the headword.

#### Scenario: One variant per sentence

- **WHEN** several Russian translations link to the same English sentence
- **THEN** at most one is kept for a headword

#### Scenario: Anchored pair preferred

- **WHEN** candidate pairs exist both with and without a sense equivalent in
  the Russian side
- **THEN** the anchored pair is kept

#### Scenario: Long-only sense still ships an example

- **WHEN** a sense's only pairs exceed the preferred length
- **THEN** the best-ranked pair is still kept

#### Scenario: Anchor-less sense falls back

- **WHEN** a sense has pairs but none contains a sense equivalent
- **THEN** the shortest pair is kept as a concordance example

#### Scenario: Single-character headword ships no examples

- **WHEN** the headword is one character long (e.g. "A" = ampere)
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

The system SHALL reuse the kaikki English build's audio stage verbatim for its
headwords — same planner, same cache, same `[s]` references and sibling
resource bundle. A headword silent in the kaikki EN build SHALL be silent here.

#### Scenario: Shared headword shares audio

- **WHEN** a headword carries recordings in the kaikki EN build
- **THEN** the bilingual article references the same recordings from its own
  sibling bundle

### Requirement: Import-ready deterministic packaging

The output SHALL be a dictzip `.dsl.dz` plus a sibling resource bundle that the
existing folder import resolves, byte-identical across rebuilds from the same
inputs. The output SHALL introduce no app, engine, or boundary change.

#### Scenario: Existing import consumes the output

- **WHEN** the produced pair is placed in an import folder
- **THEN** the app indexes and renders it with no code change

#### Scenario: Deterministic rebuild

- **WHEN** the tool runs twice on the same inputs
- **THEN** the two outputs are byte-identical

### Requirement: Sample and preview output

The system SHALL provide a sample mode emitting a bounded headword subset and a
preview rendering the sample's articles in human-readable form, deterministic
for the same inputs.

#### Scenario: Sample is reproducible

- **WHEN** the tool runs twice with the same sample inputs
- **THEN** the two samples contain the same headwords

### Requirement: Examples-only cards

The system SHALL support cards with no senses: a headword followed by up to a
stated number of example pairs rendered flat — no collapsible zone, since the
pairs are the whole article — with each English line marked `[ex]` and each
Russian line marked `[trn]`, for the sentence-example dictionary. Sense
requirements do not apply to such cards.

#### Scenario: Pairs-only card renders

- **WHEN** a headword has selected pairs but no equivalents
- **THEN** the card shows the pairs as flat `[ex]`/`[trn]` lines with no sense
  numbering and no definition lines

### Requirement: Pairs headword eligibility

A pairs-dictionary headword MUST start with a Unicode letter; anything else
(stray quotes, suffix fragments, bare numbers) is dropped and counted.
Headwords differing only in case merge into one card: the lowercase form wins
when it occurs as a whole word in the card's own pairs, otherwise the
capitalized form stands. Headwords with no pairs are omitted and counted.

#### Scenario: Junk headword dropped

- **WHEN** a candidate headword starts with a non-letter
- **THEN** no card is emitted for it and the run counts it as ill-shaped

#### Scenario: Case variants merge

- **WHEN** several candidate headwords differ only in case
- **THEN** one card is emitted, named for the lowercase form when the pairs
  spell it lowercase and for the capitalized form otherwise

### Requirement: Provenance and licensing

Every produced dictionary SHALL embed attribution, license terms, and pinned
versions for every source it was built from: equivalents name Princeton
WordNet and the RuWordNet non-commercial terms; examples name Tatoeba CC BY;
audio names the kaikki snapshot. This lands in the dictionary metadata, an
about article, and a sibling annotation file. The about article SHALL state the
output is for non-commercial use and distribution only.

#### Scenario: Attribution is embedded

- **WHEN** a dictionary is produced
- **THEN** its metadata, about article, and annotation name each used source,
  its license, and its pinned version
