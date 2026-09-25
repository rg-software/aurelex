## Purpose

Turns a pinned kaikki.org Wiktionary extract into an offline DSL dictionary for
a chosen language pair (for example `en/en` or `en/ru`), packaged so it imports
into Aurelex through the existing folder import with article content,
grammatical forms, bounded pronunciation audio, and required attribution.

## ADDED Requirements

### Requirement: Reproducible snapshot acquisition

The system SHALL build a dictionary only from a pinned kaikki.org snapshot
identified by an explicit dump date or version, so the same snapshot always
yields the same source data. It SHALL download the wiktextract source data and,
when audio is required, the Wiktionary audio archive, and MUST NOT re-download
data that is already present locally.

#### Scenario: Pinned snapshot is recorded

- **WHEN** the tool builds a dictionary
- **THEN** the output records the source snapshot's dump date/version and the
  extraction provenance used to produce it

#### Scenario: Locally cached data is reused

- **WHEN** the required source data for the pinned snapshot is already present
  in the local cache
- **THEN** the tool uses the cached data and does not download it again

#### Scenario: Audio download is skipped when audio is disabled

- **WHEN** the tool runs with audio disabled
- **THEN** it does not download the Wiktionary audio archive

### Requirement: Language-pair selection

The system SHALL accept a source language, which is the language of the indexed
headwords, and a target language, which is the language of the rendered glosses
and translations. The source language MAY equal the target language, which
denotes a monolingual dictionary. For a pair that the snapshot cannot satisfy,
the system SHALL report the pair as unsupported instead of producing an empty or
misleading dictionary.

#### Scenario: Monolingual pair

- **WHEN** the user requests source equal to target (for example `en/en`)
- **THEN** the output indexes base-form headwords of that language with their
  definitions in that language

#### Scenario: Bilingual pair

- **WHEN** the user requests a distinct target language (for example `en/ru`)
- **THEN** the output includes the target-language translations available for
  each rendered sense

#### Scenario: Unsupported pair

- **WHEN** the user requests a pair for which the snapshot has no matching
  headwords
- **THEN** the tool reports the pair as unsupported and produces no dictionary

### Requirement: Base-form headword selection

Indexed headwords SHALL be base forms by default. Entries that are inflected
forms of another word MUST NOT be indexed as headwords by default. The
inflected forms of a base word SHALL instead be rendered inside that base word's
article.

#### Scenario: Base form is indexed

- **WHEN** the snapshot contains a lemma entry for a word
- **THEN** that word is indexed as a headword

#### Scenario: Inflected form is not indexed by default

- **WHEN** the snapshot contains only an inflected form of a word (for example
  `ran` as a form of `run`) and inflected-form indexing is not enabled
- **THEN** the inflected form is not indexed as a headword

#### Scenario: Forms appear inside the base article

- **WHEN** an article is rendered for a base form
- **THEN** the article shows the grammatical/inflected forms of that base word

### Requirement: Opt-in inflected-form indexing

The system SHALL provide an opt-in mode that indexes inflected forms as
additional headwords of their base word's article, so a lookup of an inflected
form resolves to the base article. The system SHALL state that enabling this
mode adds those forms to the headword suggestion list.

#### Scenario: Inflected-form lookup resolves to the base article

- **WHEN** inflected-form indexing is enabled and the user looks up an
  inflected form
- **THEN** the base word's article is returned

#### Scenario: Disabled by default

- **WHEN** the tool runs without the inflected-form option
- **THEN** inflected forms are not indexed and do not appear in suggestions

### Requirement: Article content

Each indexed headword article SHALL include the word's parts of speech and its
glosses, the grammatical forms of the base word, and, where the source provides
them, examples. For a bilingual pair it SHALL also include the target-language
translations associated with the rendered senses.

#### Scenario: Monolingual article content

- **WHEN** an article is rendered for a monolingual pair
- **THEN** it shows the word's parts of speech, glosses, examples where present,
  and its grammatical forms

#### Scenario: Bilingual article content

- **WHEN** an article is rendered for a bilingual pair
- **THEN** it additionally shows the target-language translations for its senses

### Requirement: Bounded pronunciation audio

The system SHALL bundle at most a configurable number of pronunciation audio
files per headword, defaulting to three, and SHALL deduplicate repeated audio
files so the same recording is not bundled more than once. Setting the limit to
zero SHALL disable audio. When audio is enabled, the system SHALL prefer
recordings for the source language and SHALL omit audio that cannot be resolved
without failing the run.

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

### Requirement: Sample and preview output

The system SHALL provide a sample mode that produces a small dictionary
containing at most N selected headwords, and SHALL provide a preview that renders
the sample's articles in a human-readable form. The sample's headwords SHALL be
selected either from the start of the snapshot or as a random subset, and the
selection SHALL be reproducible so repeated runs on the same snapshot and options
produce the same sample. The sample MUST be small enough to review the article
shape and formatting before a full run.

#### Scenario: Sample contains a bounded subset

- **WHEN** the user requests a sample of N headwords
- **THEN** the output contains at most N headwords

#### Scenario: Random sample is reproducible

- **WHEN** the user requests a random sample and the tool is run twice with the
  same snapshot and options
- **THEN** the two samples contain the same headwords

#### Scenario: Preview renders articles

- **WHEN** the user requests a preview
- **THEN** the tool renders the sample's articles in a human-readable form for
  review

### Requirement: Provenance and attribution

Every produced dictionary SHALL embed attribution that identifies Wiktionary as
the source, states the CC BY-SA 4.0 license, cites wiktextract, and records the
source snapshot's dump date. This attribution SHALL appear both in the
dictionary's metadata and in an about article inside the dictionary.

#### Scenario: Metadata carries attribution

- **WHEN** a dictionary is produced
- **THEN** its metadata names Wiktionary, the CC BY-SA 4.0 license, wiktextract,
  and the snapshot dump date

#### Scenario: About article carries attribution

- **WHEN** the produced dictionary is opened
- **THEN** an about article presents the same attribution and license

### Requirement: Import-ready, deterministic packaging

The output SHALL be a single dictzip-compressed DSL dictionary file (`.dsl.dz`).
The system SHALL NOT emit an uncompressed `.dsl` file as part of its normal
output. Referenced audio SHALL be bundled as a sibling resource that the app's
DSL resource resolution finds, either inside a single resource archive or in a
resource directory, and the archive form SHALL be used by default to avoid a
large number of loose files. Rebuilding from the same snapshot and options SHALL
produce byte-identical output.

#### Scenario: Compressed dictionary file is emitted

- **WHEN** the tool produces a dictionary
- **THEN** the dictionary is a dictzip-compressed `.dsl.dz` file and no
  uncompressed `.dsl` file is emitted

#### Scenario: Audio is bundled as a resource archive

- **WHEN** the tool bundles audio with the default packaging
- **THEN** the referenced audio is placed in a single sibling resource archive
  that the app resolves when the dictionary is imported

#### Scenario: Audio can be bundled as a resource directory

- **WHEN** the tool is asked to bundle audio as loose files
- **THEN** the referenced audio is placed in a sibling resource directory that
  the app resolves when the dictionary is imported

#### Scenario: Deterministic rebuild

- **WHEN** the tool is run twice with the same snapshot and options
- **THEN** the two outputs are byte-identical

### Requirement: Data-quality reporting and resilience

Malformed or unusable source records MUST NOT abort the run. The system SHALL
skip such records and report counts of records kept and skipped, and of audio
files referenced but not found. Entries that are not lexical headwords, such as
soft redirects and romanizations, SHALL be excluded from the output.

#### Scenario: Malformed record is skipped

- **WHEN** the source contains a malformed or unparseable record
- **THEN** the tool skips it and continues, and the final report counts it

#### Scenario: Non-lexical entries are excluded

- **WHEN** the source contains soft redirects or romanization entries
- **THEN** those entries are not emitted as headwords in the output
