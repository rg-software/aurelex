# Spec Delta

## Purpose

Correct the pairs-dictionary article shape to what review and the real reader
verified: flat pairs, marked translations, and a headword eligibility rule.

## MODIFIED Requirements

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

## ADDED Requirements

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
