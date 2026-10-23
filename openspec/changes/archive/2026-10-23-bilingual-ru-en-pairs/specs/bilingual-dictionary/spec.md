# Spec Delta

## Purpose

Generalize the pairs dictionary for both directions and correct one stale
clause left by an earlier fix.

## MODIFIED Requirements

### Requirement: Examples-only cards

The system SHALL support cards with no senses: a headword followed by up to
a stated number of example pairs rendered flat — no collapsible zone, since
the pairs are the whole article — with each source-language line marked
`[ex]` and each target-language line marked `[trn]`, for the
sentence-example dictionary. Sense requirements do not apply to such cards.
The build direction is a parameter (English→Russian or Russian→English).

#### Scenario: Pairs-only card renders

- **WHEN** a headword has selected pairs but no equivalents
- **THEN** the card shows the pairs as flat `[ex]`/`[trn]` lines with no sense
  numbering and no definition lines

#### Scenario: Reversed direction renders

- **WHEN** the build direction is Russian→English
- **THEN** the Russian line of each pair is marked `[ex]` and the English
  line is marked `[trn]`

### Requirement: Pairs headword eligibility

A pairs-dictionary headword MUST start with a Unicode letter; anything else
(stray quotes, suffix fragments, bare numbers) is dropped and counted.
The candidate universe is the source-language kaikki snapshot. Headwords
differing only in case merge into one card: the lowercase form wins when it
occurs as a whole word in the card's own pairs, otherwise the capitalized
form stands. Headwords with no pairs are omitted and counted.

#### Scenario: Junk headword dropped

- **WHEN** a candidate headword starts with a non-letter
- **THEN** no card is emitted for it and the run counts it as ill-shaped

#### Scenario: Case variants merge

- **WHEN** several candidate headwords differ only in case
- **THEN** one card is emitted, named for the lowercase form when the pairs
  spell it lowercase and for the capitalized form otherwise

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

### Requirement: Provenance and licensing

Every produced dictionary SHALL embed attribution, license terms, and pinned
versions for every source it was built from: equivalents name Princeton
WordNet and the RuWordNet non-commercial terms; examples name Tatoeba CC BY;
audio names the kaikki snapshot. This lands in the dictionary metadata, an
about article, and a sibling annotation file. The about article SHALL state
the output is for non-commercial use and distribution only. The attribution
SHALL name the build direction (English→Russian or Russian→English).

#### Scenario: Attribution is embedded

- **WHEN** a dictionary is produced
- **THEN** its metadata, about article, and annotation name each used source,
  its license, and its pinned version

#### Scenario: Reversed dictionary names its direction

- **WHEN** the build direction is Russian→English
- **THEN** the about article and annotation describe a Russian-English
  dictionary built from Tatoeba rus-eng pairs
