## ADDED Requirements

### Requirement: Title separate from output name

The system SHALL accept a display title separate from the output name. The title
SHALL be used for the dictionary's name metadata, the about article's headword,
and the description heading, while the output file names (the dictionary, its
resource bundle, and its annotation) SHALL use the output name. When no title is
given, the output name SHALL be used as the title.

#### Scenario: A title differs from the file name

- **WHEN** the tool is run with a title and an output name
- **THEN** the output files use the output name, and the name metadata, the about
  article's headword, and the description heading use the title

#### Scenario: The title defaults to the output name

- **WHEN** no title is given
- **THEN** the title is the output name

## MODIFIED Requirements

### Requirement: Provenance and attribution

Every produced dictionary SHALL embed attribution that identifies Wiktionary as
the source, states the CC BY-SA 4.0 license, cites wiktextract, and records the
source snapshot's dump date. This attribution SHALL appear in the dictionary's
metadata, in an about article inside the dictionary whose headword is the
dictionary's title, and in a sibling annotation file beside the dictionary. The
about article and the annotation SHALL present the same description — the title,
that the dictionary is a derivative work of Wiktionary (via kaikki.org) at the
snapshot date, the wiktextract reference, the license, and the language — and the
about article SHALL additionally carry the sense-icon legend.

#### Scenario: Metadata carries attribution

- **WHEN** a dictionary is produced
- **THEN** its metadata names Wiktionary, the CC BY-SA 4.0 license, wiktextract,
  and the snapshot dump date

#### Scenario: About article carries attribution

- **WHEN** the produced dictionary is opened
- **THEN** an about article presents the same description and the sense-icon
  legend

#### Scenario: The about article names the dictionary

- **WHEN** a dictionary is produced with a title
- **THEN** its about article's headword is that title, so several produced
  dictionaries do not share one about headword

#### Scenario: A sibling annotation carries the attribution

- **WHEN** a dictionary is produced
- **THEN** a plain-text annotation file sits beside it carrying the same
  description as the about article
