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

### Requirement: Language selection

The system SHALL build a monolingual dictionary: the indexed headwords and their
glosses SHALL be in the same language, taken from the data edition for that
language. The language SHALL be selected explicitly, and only records of that
language SHALL contribute to the output. A language the snapshot cannot satisfy
SHALL be reported as unsupported rather than producing an empty or misleading
dictionary.

#### Scenario: Monolingual dictionary

- **WHEN** the tool builds for a language from that language's data edition
- **THEN** the indexed headwords and their glosses are in the same language

#### Scenario: Records of another language are excluded

- **WHEN** the snapshot holds, for the same spelling, a record of a different
  language alongside the source-language one (even when the other record carries
  nested data that names the source language)
- **THEN** only the source-language record contributes to the article

#### Scenario: Unsupported language

- **WHEN** the snapshot has no records for the requested language
- **THEN** the tool reports the language as unsupported and produces no dictionary

### Requirement: Source-language profiles

The system SHALL carry a profile for each supported source language, describing
its grammatical form vocabulary and short labels, the display labels for its
parts of speech, the tags that disqualify a form, the pronunciation fields to
prefer, and how its sense tags are presented (their abbreviations, and the ones
that are not shown). A source language without a profile SHALL fall back to a
permissive default and SHALL report that it is doing so. English, German,
Japanese and Russian SHALL have profiles.

#### Scenario: A language with a profile needs no fallback

- **WHEN** the tool builds with a source language that has a profile
- **THEN** it does not report a missing-profile fallback

#### Scenario: A part of speech is shown in the dictionary's language

- **WHEN** a record's part of speech is rendered and the profile has a label for
  it
- **THEN** the label is shown instead of the raw source code

#### Scenario: A sense tag is shown in the dictionary's language

- **WHEN** a sense tag is shown as text
- **THEN** it uses the profile's abbreviation for that tag

#### Scenario: Grammatical forms use the language's labels

- **WHEN** a form carries grammatical tags the profile knows
- **THEN** it is shown with the profile's short labels for those tags

#### Scenario: A form the profile disqualifies is not shown

- **WHEN** a form carries only tags the profile treats as noise (table
  machinery, a transliteration, or the canonical lemma entry)
- **THEN** that form is not listed on the article

#### Scenario: A form with no recognised label is not shown

- **WHEN** a form's tags are outside the profile's grammatical vocabulary and are
  not disqualifying tags either
- **THEN** that form is not listed on the article

#### Scenario: Russian uses its own profile

- **WHEN** the tool builds with `--source-lang ru`
- **THEN** no missing-profile fallback is reported, and Russian parts of speech,
  forms and sense tags are labelled with the Russian profile's terms

#### Scenario: A language without a profile falls back and reports it

- **WHEN** the tool builds with a source language that has no profile
- **THEN** it reports that it is using a permissive default

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

### Requirement: Article body

Each indexed headword article SHALL include the word's parts of speech and its
glosses, the grammatical forms of the base word, and, where the source provides
them, examples.

#### Scenario: Article content

- **WHEN** an article is rendered
- **THEN** it shows the word's parts of speech, glosses, examples where present,
  and its grammatical forms

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
the base word's listed forms. A cross-reference bookkeeping example SHALL NOT be
kept. An archaic example (Early Modern or Middle English spelling or inflection)
SHALL NOT be kept for a sense that is not marked obsolete, dated or archaic; for
a sense that is so marked, an archaic example SHALL be shown when no other
qualifying example exists, so such a sense is illustrated rather than left bare,
and a modern-readable example SHALL be preferred when one exists. An example
longer than a fixed bound SHALL be shortened at a word boundary.

#### Scenario: Example must use the headword

- **WHEN** a source example does not contain the headword or any of its listed
  forms
- **THEN** that example is not shown

#### Scenario: Archaic and citation examples are dropped

- **WHEN** a sense that is not marked obsolete, dated or archaic has an archaic
  quotation or a cross-reference bookkeeping example
- **THEN** that example is not shown

#### Scenario: An archaic sense falls back to an archaic example

- **WHEN** a sense is marked obsolete, dated or archaic and it has an archaic
  example but no modern-readable one
- **THEN** the archaic example is shown, shortened if it exceeds the bound

#### Scenario: An archaic sense prefers a modern-readable example

- **WHEN** a sense is marked obsolete, dated or archaic and it has both a
  modern-readable example and an archaic one
- **THEN** the modern-readable example is shown

#### Scenario: A bookkeeping example is dropped even on an archaic sense

- **WHEN** a sense is marked obsolete, dated or archaic and its only example is a
  cross-reference bookkeeping line
- **THEN** that example is not shown

#### Scenario: An over-long example is shortened

- **WHEN** a qualifying example exceeds the length bound
- **THEN** it is cut at a word boundary that fits the bound

### Requirement: Linked related headwords

When a source sense states that a word is an alternative or other form of another
headword, the system SHALL render that related headword as a link the reader can
tap to open its article. The link SHALL be emitted only when the produced
dictionary actually contains the related headword, so no link points at an entry
that does not exist. A related headword named by more than one relation SHALL be
linked once, never nested inside another link. The related headword SHALL NOT be
added as a separate cross-reference when it is already linked inside the sense's
gloss.

#### Scenario: An alternative form links to its base headword

- **WHEN** the source renders a sense as an alternative or other form of a
  headword that the dictionary contains
- **THEN** that headword appears as a tappable link within the sense

#### Scenario: No link to an absent headword

- **WHEN** a sense names a related headword that the produced dictionary does not
  contain
- **THEN** the headword is left as plain text and no link is emitted

#### Scenario: A target named by several relations is linked once

- **WHEN** a sense names the same related headword in both its alternative-form
  and form-of relations
- **THEN** the headword appears as a single link, not a link inside a link

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

### Requirement: Optional reuse of an existing resource bundle

The system SHALL provide an option to render the dictionary without rebuilding
its resource bundle, leaving the bundle already present beside the dictionary as
it is. When this option is used, the system SHALL verify that the existing bundle
contains every resource the produced dictionary references and SHALL report any
referenced resource that the bundle lacks, or the absence of a bundle, rather
than leaving a broken reference silently.

#### Scenario: An existing complete bundle is reused

- **WHEN** the option is given and the resource bundle beside the dictionary
  already contains every resource the rendered dictionary references
- **THEN** the dictionary is written, the resource bundle is left unchanged, and
  the run reports the reuse

#### Scenario: A referenced resource is missing from the reused bundle

- **WHEN** the option is given and the existing bundle lacks a resource the
  rendered dictionary references
- **THEN** the run warns and states how many referenced resources are missing

#### Scenario: No bundle to reuse

- **WHEN** the option is given and there is no resource bundle beside the
  dictionary
- **THEN** the run warns that the dictionary's referenced resources are not
  present

#### Scenario: The bundle is rebuilt when the option is not given

- **WHEN** the option is not given
- **THEN** the resource bundle is rebuilt from the cache and archive as before
