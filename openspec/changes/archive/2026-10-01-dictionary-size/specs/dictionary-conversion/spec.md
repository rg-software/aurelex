## ADDED Requirements

### Requirement: Stated dictionary size

The produced dictionary SHALL state the number of entries (headword cards) it
contains, both in its about article and in its sibling annotation file.

#### Scenario: The about article states the size

- **WHEN** the produced dictionary is opened
- **THEN** its about article states how many entries the dictionary contains

#### Scenario: The annotation states the size

- **WHEN** a dictionary is produced
- **THEN** its sibling annotation file states how many entries the dictionary
  contains

#### Scenario: The size counts entries, not the about article

- **WHEN** the stated size is counted
- **THEN** it is the number of headword cards, not including the about article
  itself
