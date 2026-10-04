## MODIFIED Requirements

### Requirement: Bounded pronunciation audio

The system SHALL bundle at most a configurable number of pronunciation audio
files per headword, defaulting to three, and SHALL deduplicate repeated audio
files so the same recording is not bundled more than once. Setting the limit to
zero SHALL disable audio. When audio is enabled, the system SHALL prefer
recordings for the source language and SHALL omit audio that cannot be resolved
without failing the run. A recording from an enabled additional audio source MAY
be bundled, in which case it SHALL fill only slots the source snapshot's own
recordings left empty, SHALL NOT displace a recording the snapshot supplied, and
SHALL count towards the same per-headword limit.

#### Scenario: Default limit
- **WHEN** the tool runs with audio enabled and the default limit
- **THEN** no headword has more than three bundled audio files

#### Scenario: Custom limit
- **WHEN** the user sets the per-headword audio limit
- **THEN** no headword has more than that many bundled audio files

#### Scenario: Audio disabled
- **WHEN** the user disables audio
- **THEN** no audio files are bundled and no audio archive is downloaded

#### Scenario: Missing audio does not fail the article
- **WHEN** a headword references audio that is absent from the archive
- **THEN** the article is still produced with its text content

#### Scenario: An additional source fills only what the snapshot left empty
- **WHEN** a headword's recordings from the snapshot do not reach the
  per-headword limit and an enabled additional audio source holds a recording of
  that headword
- **THEN** the headword's article references the additional recording and the
  total stays within the limit

#### Scenario: The per-headword limit holds across sources
- **WHEN** a headword's recordings come from both the snapshot and enabled
  additional audio sources
- **THEN** no headword has more bundled audio files than the configured limit

### Requirement: Provenance and attribution

Every produced dictionary SHALL embed attribution that identifies Wiktionary as
the source, states the CC BY-SA 4.0 license, cites wiktextract, and records the
source snapshot's dump date. This attribution SHALL appear in the dictionary's
metadata, in an about article inside the dictionary whose headword is the
dictionary's title, and in a sibling annotation file beside the dictionary. The
about article and the annotation SHALL present the same description — the title,
that the dictionary is a derivative work of Wiktionary (via kaikki.org) at the
snapshot date, the wiktextract reference, the license, and the language — and
the about article SHALL additionally carry the sense-icon legend. When the
dictionary bundles recordings from an additional audio source, that description
SHALL additionally name every contributing source with its license and state
where the credit for each individual recording is recorded.

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

#### Scenario: Additional sources are named with their licenses

- **WHEN** a dictionary bundles recordings from one or more additional audio
  sources
- **THEN** its about article and its sibling annotation name each contributing
  source with that source's license and state where the credit for an individual
  recording is recorded

#### Scenario: A snapshot-only dictionary's attribution is unchanged

- **WHEN** a dictionary bundles no recording from an additional audio source
- **THEN** its description carries the same attribution as before, with no
  additional source named