## ADDED Requirements

### Requirement: One card per headword

The system SHALL emit exactly one article per indexed headword. When the source
snapshot holds records for one headword that are not adjacent in file order, the
system SHALL merge them into that single article instead of emitting a second
card, and the result SHALL NOT depend on the order in which the records appear.

#### Scenario: Non-adjacent records merge

- **WHEN** a headword's source records are separated in the snapshot by records
  of other headwords
- **THEN** the headword's article is emitted once and carries the content of all
  those records

#### Scenario: Adjacent records still merge

- **WHEN** a headword's source records are adjacent in the snapshot
- **THEN** they are emitted as one article, as before

#### Scenario: The merge is reported

- **WHEN** a build merges records for a headword that were not adjacent
- **THEN** the final report counts the headwords so merged

### Requirement: Cards carry a definition

The system SHALL NOT emit an article that has no definition, unless another
emitted article links to that headword. A headword whose rendered article has no
gloss and is not linked by any emitted article SHALL be omitted from the
dictionary; one that is linked SHALL be kept so the link resolves. The system
SHALL report how many articles were omitted for lack of a definition.

#### Scenario: A definition-less, unlinked card is omitted

- **WHEN** a headword's article would contain no gloss and no other article links
  to that headword
- **THEN** that headword is not emitted and the run counts it

#### Scenario: A linked definition-less card is kept

- **WHEN** a headword's article would contain no gloss but another emitted
  article links to that headword
- **THEN** the article is kept so the link resolves

#### Scenario: The omission is reported

- **WHEN** a build omits one or more definition-less articles
- **THEN** the final report states how many were omitted

### Requirement: No dangling headword links

The system SHALL NOT emit a link to a headword that the produced dictionary does
not contain. When a link would target a headword that is not emitted, the system
SHALL render the target as plain text instead, and SHALL report the number of
links so unlinked.

#### Scenario: A link to an absent headword is left as text

- **WHEN** an article would link to a headword that the dictionary does not
  contain
- **THEN** the target appears as plain text with no link

#### Scenario: The unlinking is reported

- **WHEN** a build leaves one or more would-be links as plain text
- **THEN** the final report states how many were unlinked
