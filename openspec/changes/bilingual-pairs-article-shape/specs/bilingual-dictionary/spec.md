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
