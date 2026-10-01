## MODIFIED Requirements

### Requirement: Provenance and attribution

Every produced dictionary SHALL embed attribution that identifies Wiktionary as
the source, states the CC BY-SA 4.0 license, cites wiktextract, and records the
source snapshot's dump date. This attribution SHALL appear in the dictionary's
metadata, in an about article inside the dictionary whose headword names the
dictionary, and in a sibling annotation file beside the dictionary for readers
that surface a dictionary description.

#### Scenario: Metadata carries attribution

- **WHEN** a dictionary is produced
- **THEN** its metadata names Wiktionary, the CC BY-SA 4.0 license, wiktextract,
  and the snapshot dump date

#### Scenario: About article carries attribution

- **WHEN** the produced dictionary is opened
- **THEN** an about article presents the same attribution and license

#### Scenario: The about article names the dictionary

- **WHEN** a dictionary is produced with a given name
- **THEN** its about article's headword includes that name, so several produced
  dictionaries do not share one about headword

#### Scenario: A sibling annotation carries the attribution

- **WHEN** a dictionary is produced
- **THEN** a plain-text annotation file sits beside it carrying the same
  attribution and the dictionary name
