# Spec Delta

## Purpose

Add the Russian→English translation direction alongside the existing
English→Russian one. The pairs direction parameter already exists; this
delta covers the translation dictionary only.

## ADDED Requirements

### Requirement: Reverse equivalent resolution

The system SHALL resolve Russian headwords through RuWordNet synsets
bridged to Princeton WordNet via `ili`: each linked EN synset becomes one
card sense with the EN member lemmas as equivalents (verbatim,
underscores rendered as spaces); fellow RU lemmas of the source synset
become the sense synonyms. A RU synset with no `ili` link SHALL resolve
unlinked: synonyms only, no equivalents, counted against coverage.

#### Scenario: RU headword resolves through ili

- **WHEN** a Russian headword's synset links to EN synsets
- **THEN** each linked EN synset is one sense with its EN lemmas as
  equivalents and the RU synset's other lemmas as synonyms

#### Scenario: Unlinked RU synset ships synonyms only

- **WHEN** a Russian headword's synset has no `ili` link
- **THEN** the sense carries synonyms but no equivalents and counts as
  unlinked

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
ships as a concordance fallback. English frequency ranks; length ranks,
never filters. Single-character headwords match no pairs.

#### Scenario: EN-anchored pair preferred

- **WHEN** candidate pairs exist both with and without a sense equivalent
  in the English side
- **THEN** the anchored pair is kept

#### Scenario: Anchor-less reverse sense falls back

- **WHEN** a reverse sense has pairs but none contains a sense equivalent
- **THEN** the shortest pair is kept as a concordance example

### Requirement: Reverse pronunciation audio

The system SHALL reuse the kaikki Russian build's audio stage verbatim for
reverse headwords — same planner, same cache, same `[s]` references and
sibling resource bundle. A headword silent in the kaikki RU build SHALL be
silent here.

#### Scenario: Shared RU headword shares audio

- **WHEN** a headword carries recordings in the kaikki RU build
- **THEN** the reverse card references the same recordings and the bundle
  carries them

## MODIFIED Requirements

### Requirement: Provenance and licensing

Every produced dictionary SHALL embed attribution, license terms, and pinned
versions for every source it was built from: equivalents name Princeton
WordNet and the RuWordNet non-commercial terms; examples name Tatoeba CC BY;
audio names the kaikki snapshot. This lands in the dictionary metadata, an
about article, and a sibling annotation file. The about article SHALL state the
output is for non-commercial use and distribution only. The attribution SHALL
name the build direction (English→Russian or Russian→English).

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
