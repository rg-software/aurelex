# dictionary-conversion Specification

## Purpose

Turns a pinned kaikki.org Wiktionary extract into an offline DSL dictionary for
a chosen language pair (for example `en/en` or `en/ru`), packaged so it imports
into Aurelex through the existing folder import with article content,
grammatical forms, bounded pronunciation audio, and required attribution.

## Requirements

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
misleading dictionary. Only records of the source language SHALL contribute to
the output.

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

#### Scenario: Records of another language are excluded

- **WHEN** the snapshot holds, for the same spelling, a record of a different
  language alongside the source-language one (even when the other record carries
  nested data that names the source language)
- **THEN** only the source-language record contributes to the article

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
output. The compressed file SHALL be readable by seeking: every chunk recorded in
its chunk index SHALL be independently inflatable, without relying on data from
any other chunk, so a reader can seek to a chunk and inflate just that chunk.
Referenced audio SHALL be bundled as a sibling resource that the app's
DSL resource resolution finds, either inside a single resource archive or in a
resource directory, and the archive form SHALL be used by default to avoid a
large number of loose files. Rebuilding from the same snapshot and options SHALL
produce byte-identical output.

#### Scenario: Compressed dictionary file is emitted
- **WHEN** the tool produces a dictionary
- **THEN** the dictionary is a dictzip-compressed `.dsl.dz` file and no
  uncompressed `.dsl` file is emitted

#### Scenario: Every chunk can be read on its own
- **WHEN** a produced dictionary's uncompressed content is larger than one chunk
- **THEN** each chunk in its chunk index inflates independently, so a reader that
  seeks to any chunk reads it without error

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

### Requirement: Card article layout

A rendered headword card SHALL present its parts of speech in first-seen order,
each with the grammatical forms of the base word and the senses of that part of
speech. Records that share a part of speech SHALL be merged into one block, so an
interleaved `noun, verb, noun` reads as one noun block followed by one verb
block. Each part of speech SHALL be separated from the one before it by a blank
line, so the sections read as distinct blocks; no blank line SHALL precede the first part of speech. When the whole card carries a
single pronunciation transcription, that transcription SHALL be shown once above
the first part of speech rather than repeated; when parts of speech differ, each
SHALL keep its own transcription under its own heading. A transcription SHALL be
shown without a notation name where it is the dictionary's primary notation (for
example IPA), because the line already reads as a transcription; a second
notation SHALL keep its name so the two are distinguishable. A headword's audio
SHALL be shown on the same line as the transcription of the part of speech it
belongs to — the transcription and its playback controls together — and where a
part of speech has audio but no transcription, that audio SHALL still be shown.
Each referenced audio file SHALL be shown at most once on the card, under the
first part of speech that references it.

#### Scenario: Same part of speech is merged

- **WHEN** a headword's records include a noun, a verb, and another noun
- **THEN** the card shows a single noun block (containing both noun records'
  senses) followed by a single verb block

#### Scenario: Shared transcription is hoisted

- **WHEN** every record of a card carries the same transcription
- **THEN** the transcription appears once above the first part of speech

#### Scenario: Differing transcriptions stay with their part of speech

- **WHEN** the records of a card carry different transcriptions
- **THEN** each part of speech shows its own transcription beneath its heading

#### Scenario: A single-record card hoists its transcription

- **WHEN** a card has one record carrying a transcription
- **THEN** the transcription is shown above the part of speech, the same as when
  several records share one transcription

#### Scenario: The primary transcription is not named

- **WHEN** an article shows the dictionary's primary transcription (IPA for the
  English profile)
- **THEN** the transcription appears on its own without an "IPA" label

#### Scenario: Audio sits on the transcription line

- **WHEN** a headword has both a transcription and audio for a part of speech
- **THEN** the audio links are shown on the same line as the transcription

#### Scenario: Parts of speech are separated

- **WHEN** a card has more than one part of speech
- **THEN** each part of speech after the first is preceded by a blank line

#### Scenario: A shared audio file is shown once

- **WHEN** two parts of speech of one card reference the same audio file
- **THEN** that audio file appears once on the card

### Requirement: Grouped sub-senses

When a source sense's definition is split into a shared parent phrase and one or
more specific parts, the parent SHALL be rendered once as a heading at one sense
level and each specific part as a sub-sense at the next level beneath it. A sense
whose definition is a single phrase SHALL be rendered as its own sense with no
sub-senses. A heading or sub-sense whose text repeats one already rendered on the
card SHALL be dropped.

A heading that carries sub-senses SHALL be numbered, in sequence within its part
of speech, so the top-level sections of a long article read as an outline. The
sequence SHALL restart for each part of speech. A sense with no sub-senses SHALL
NOT be numbered.

#### Scenario: Shared parent renders once

- **WHEN** several senses of a headword share a parent phrase with different
  specific parts
- **THEN** the parent phrase is rendered once as a heading and each specific part
  is rendered beneath it

#### Scenario: Single-phrase sense has no sub-senses

- **WHEN** a sense's definition is a single phrase
- **THEN** it is rendered as its own sense, with no parent heading

#### Scenario: Repeated text is not repeated

- **WHEN** the source repeats a definition verbatim across senses
- **THEN** the repeated text is rendered only once on the card

#### Scenario: Group headings are numbered within their part of speech

- **WHEN** a part of speech has two or more sense headings that carry sub-senses
- **THEN** they are numbered in sequence from one, and the numbering starts again
  at one for the next part of speech

#### Scenario: A sense without sub-senses is not numbered

- **WHEN** a sense has no sub-senses
- **THEN** it is shown without a sequence number

### Requirement: Sense tag display

For each rendered sense, the system SHALL represent a fixed set of common tags as
small inline icons in place of text — a countable icon, an uncountable icon, a
tag/label icon for initialism/abbreviation relations, and a building/landmark
icon for obsolete, dated, and archaic usage — and SHALL NOT render those tags as
text. A sense tagged as an alternative or other form SHALL render no marker: its
gloss already states the relation, and the related headword is linked instead
(see Linked related headwords). It SHALL render at most one remaining
register/context tag as abbreviated text per sense. Tags that state an
unremarkable grammatical case (transitive, intransitive, not comparable) and
tags whose meaning the gloss already carries through a relation stated in the
gloss itself (synonym, ellipsis, clipping) SHALL NOT be rendered.

A countability icon SHALL be shown only when exactly one of countable or
uncountable applies to the sense; when the source marks a sense as both — the
common case for nouns that can be either — neither countability icon SHALL be
shown.

When a gloss opens with a relation phrase that a displayed icon already conveys
(an initialism, abbreviation or acronym, as in "Initialism of …"), the system
SHALL omit that phrase from the gloss and keep the rest, so the gloss is not
saying what the icon already says.

#### Scenario: Countability is shown as an icon

- **WHEN** a sense is tagged countable or uncountable but not both
- **THEN** the sense shows the corresponding icon and not the word itself

#### Scenario: A sense that is both countable and uncountable shows neither icon

- **WHEN** a sense is tagged both countable and uncountable
- **THEN** the sense shows no countability icon

#### Scenario: An alternative-form sense shows no marker

- **WHEN** a sense is tagged as an alternative or other form
- **THEN** the sense shows no icon and no text tag for that relation

#### Scenario: The phrase a relation icon conveys is dropped from the gloss

- **WHEN** a sense is tagged as an initialism and its gloss reads "Initialism of
  <headword>."
- **THEN** the article shows the initialism icon followed by the headword, with
  no "Initialism of" wording

#### Scenario: A relation without an icon keeps its words

- **WHEN** a sense's gloss names a relation that is not shown as an icon (for
  example a clipping)
- **THEN** that wording is kept in the gloss

#### Scenario: Alternative and initialism relations are shown as icons

- **WHEN** a sense is tagged as an initialism or abbreviation
- **THEN** the sense shows the corresponding relation icon and not the word
  itself

#### Scenario: Obsolete and dated usage is shown as an icon

- **WHEN** a sense is tagged obsolete, dated, or archaic
- **THEN** the sense shows the usage icon and not the word itself

#### Scenario: A register tag is shown as abbreviated text

- **WHEN** a sense carries a register or context tag outside the icon set (for
  example figuratively, derogatory, or regional)
- **THEN** that tag is shown as abbreviated text and not as an icon

#### Scenario: An unremarkable-case tag is not shown

- **WHEN** a sense is tagged transitive, intransitive, or not comparable
- **THEN** that tag is not rendered in the article

#### Scenario: An icon and a register tag coexist

- **WHEN** a sense carries both a tag from the icon set and a register tag
- **THEN** the article shows the icon followed by the abbreviated register tag

### Requirement: Sense bullets

Each leaf sense SHALL be preceded by a visible bullet so that sibling senses are
visually separated. A sense that heads one or more sub-senses SHALL NOT be
bulleted; its sub-senses SHALL be.

#### Scenario: Sibling senses are bulleted

- **WHEN** a headword has several sibling senses
- **THEN** each sibling sense begins with a bullet

#### Scenario: A sub-sense heading is not bulleted

- **WHEN** a sense heads sub-senses
- **THEN** that heading is not bulleted and each sub-sense beneath it is

### Requirement: Per-sense examples

Each sense SHALL carry its own examples, when the source provides any that
qualify, inside a collapsed optional zone placed directly beneath that sense, so
an example stays with the use it illustrates rather than being pooled at the
card. A sense SHALL keep at most one qualifying example. A sense with no
qualifying example SHALL have no optional zone. Examples and cross-references are
the only content placed in optional zones.

An optional zone SHALL be closed with a tag the DSL reader recognises, and the
zone SHALL NOT enclose any following sense: the reader nests content by tag name
and silently ignores a closing tag with no matching opening tag, so a wrong
closer would leave every later sense inside the zone and collapse it with it.

#### Scenario: An example stays with its sense

- **WHEN** a sense's source record provides a qualifying example
- **THEN** that example appears in an optional zone directly beneath that sense's
  definition

#### Scenario: At most one example per sense

- **WHEN** a sense's source record provides several qualifying examples
- **THEN** at most one example is kept for that sense

#### Scenario: No example leaves no empty zone

- **WHEN** a sense has no qualifying example
- **THEN** no optional zone is rendered for that sense

#### Scenario: A following sense is outside the zone

- **WHEN** a sense with an example is followed by another sense
- **THEN** the following sense is not inside the first sense's optional zone and
  is visible when the zones are collapsed

#### Scenario: An optional zone is closed with a recognised tag

- **WHEN** an optional zone is emitted
- **THEN** it is closed with a tag the reader treats as closing that zone

### Requirement: Example qualification

An example SHALL be kept for a sense only when it contains the headword or one of
the base word's listed forms. Examples that are archaic (Early Modern or Middle
English spelling or inflection) or that are cross-reference bookkeeping pointing
at another entry SHALL NOT be kept. An example longer than a fixed bound SHALL be
shortened at a word boundary.

#### Scenario: Example must use the headword

- **WHEN** a source example does not contain the headword or any of its listed
  forms
- **THEN** that example is not shown

#### Scenario: Archaic and citation examples are dropped

- **WHEN** a source example is an archaic quotation or a cross-reference
  bookkeeping line
- **THEN** that example is not shown

#### Scenario: An over-long example is shortened

- **WHEN** a qualifying example exceeds the length bound
- **THEN** it is cut at a word boundary that fits the bound

### Requirement: Linked related headwords

When a source sense states that a word is an alternative or other form of another
headword, the system SHALL render that related headword as a link the reader can
tap to open its article. The link SHALL be emitted only when the produced
dictionary actually contains the related headword, so no link points at an entry
that does not exist. The related headword SHALL NOT be added as a separate
cross-reference when it is already linked inside the sense's gloss.

#### Scenario: An alternative form links to its base headword

- **WHEN** the source renders a sense as an alternative or other form of a
  headword that the dictionary contains
- **THEN** that headword appears as a tappable link within the sense

#### Scenario: No link to an absent headword

- **WHEN** a sense names a related headword that the produced dictionary does not
  contain
- **THEN** the headword is left as plain text and no link is emitted

#### Scenario: The related headword is not duplicated as a cross-reference

- **WHEN** a sense already links the headword it is a form of
- **THEN** that headword is not also listed in the card's cross-reference list

### Requirement: Cross-references

Related entries SHALL be shown once per card as a de-duplicated, bounded list in
a single card-level optional zone, not repeated per part of speech or per sense.

#### Scenario: Cross-references appear once

- **WHEN** several parts of speech of a card yield related-entry references
- **THEN** the article shows one cross-reference list for the whole card

### Requirement: Self-contained sense markers

The icons used as sense markers SHALL be bundled inside the produced dictionary's
own resource bundle and SHALL render with no network access. The icons SHALL be
identical across builds of the same inputs, so the deterministic-output guarantee
holds. The dictionary SHALL still bundle these icons when audio is disabled.

#### Scenario: Icon renders offline

- **WHEN** an article containing a sense icon is viewed with no network access
- **THEN** the icon renders

#### Scenario: Icons are bundled with audio disabled

- **WHEN** the tool runs with audio disabled
- **THEN** the sense icons are still bundled with the dictionary
