# Spec Delta

## Purpose

Omit content-free senses (neither equivalents nor a definition) from
articles in both translation directions. Resolve-level counting is
unchanged.

## MODIFIED Requirements

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
