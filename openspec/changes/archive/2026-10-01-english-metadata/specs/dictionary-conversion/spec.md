## ADDED Requirements

### Requirement: English metadata

A produced dictionary's metadata SHALL be in English: its language fields, its
about article and its annotation SHALL name the language in English, whatever
language the data edition is in, so a reader that matches language names
recognises it. A language not in the metadata's name table SHALL fall back to the
source's own name for it. The dictionary's content (headwords, glosses and their
labels) SHALL remain in the dictionary's language.

#### Scenario: A non-English edition names the language in English

- **WHEN** a dictionary is built from an edition whose records name the language
  in their own language
- **THEN** its language fields, about article and annotation name the language in
  English

#### Scenario: An unlisted language falls back to its source name

- **WHEN** the language is not in the metadata's name table
- **THEN** the source's own name for it is used

#### Scenario: The content is unaffected

- **WHEN** a non-English dictionary is built
- **THEN** its headwords, glosses, parts of speech and form labels stay in the
  dictionary's language
