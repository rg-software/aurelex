## MODIFIED Requirements

### Requirement: Source-language profiles

The system SHALL carry a profile for each supported source language, describing
its grammatical form vocabulary and short labels, the display labels for its
parts of speech, the tags that disqualify a form, the pronunciation fields to
prefer, and how its sense tags are presented (their abbreviations, and the ones
that are not shown). A profile SHALL also declare whether the language has
pronunciation recordings at all; a language without them SHALL NOT cause the
audio archive to be fetched, in the build or in the pre-fetcher. A profile MAY
declare which form tags are readings rather than inflections, the mark each
reading's origin tag groups under, and the mark a reading with no origin prints
under, so a language whose readings are recorded as forms (Japanese) does not
show them as inflections. A source language without a profile SHALL fall back to
a permissive default and SHALL report that it is doing so. English, German,
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

#### Scenario: A language whose readings are forms declares them

- **WHEN** the profile declares which form tags are readings
- **THEN** those forms are treated as readings and not listed as inflections

#### Scenario: Russian uses its own profile

- **WHEN** the tool builds with `--source-lang ru`
- **THEN** no missing-profile fallback is reported, and Russian parts of speech,
  forms and sense tags are labelled with the Russian profile's terms

#### Scenario: Japanese uses its own profile

- **WHEN** the tool builds with `--source-lang ja`
- **THEN** no missing-profile fallback is reported, and Japanese parts of speech,
  forms and sense tags are labelled with the Japanese profile's terms

#### Scenario: A language with no recordings skips the archive

- **WHEN** the language's profile declares no pronunciation recordings
- **THEN** the build does not download the audio archive and bundles no audio

#### Scenario: A language without a profile falls back and reports it

- **WHEN** the tool builds with a source language that has no profile
- **THEN** it reports that it is using a permissive default

### Requirement: Card article layout

A rendered headword card SHALL present its parts of speech in first-seen order,
each with the grammatical forms of the base word and the senses of that part of
speech, and, where the profile declares reading forms, the word's readings
grouped under the profile's marks on a line of their own. Records that share a
part of speech SHALL be merged into one block, so an
interleaved `noun, verb, noun` reads as one noun block followed by one verb
block. Each part of speech SHALL be separated from the one before it by a blank
line, so the sections read as distinct blocks; no blank line SHALL precede the first part of speech. When the whole card carries a
single pronunciation transcription, that transcription SHALL be shown once above
the first part of speech rather than repeated; when parts of speech differ, each
SHALL keep its own transcription under its own heading. A transcription SHALL be
shown without a notation name where it is the dictionary's primary notation (for
example IPA), because the line already reads as a transcription; a second
notation SHALL keep its name so the two are distinguishable. A sound whose tags
name a different notation SHALL NOT be shown as the notation its field claims. A
headword's audio
SHALL be shown on the same line as the transcription of the part of speech it
belongs to — the transcription and its playback controls together — and where a
part of speech has audio but no transcription, that audio SHALL still be shown.
Each referenced audio file SHALL be shown at most once on the card, under the
first part of speech that references it.

#### Scenario: Same part of speech is merged

- **WHEN** a headword's records include a noun, a verb, and another noun
- **THEN** the card shows a single noun block (containing both noun records'
  senses) followed by a single verb block

#### Scenario: Readings are grouped and left off the forms line

- **WHEN** a card's records carry reading forms the profile declares
- **THEN** the readings appear grouped under their marks on their own line, and
  the forms line holds only inflections

#### Scenario: Readings shared across a card are shown once

- **WHEN** every record of a card carries the same readings
- **THEN** the readings line appears once, above the first part of speech

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

#### Scenario: A sound in another notation is not shown as this one

- **WHEN** a record carries a value under the primary notation's field but the
  sound's tags name a different notation
- **THEN** that value is not shown as the primary notation

#### Scenario: Audio sits on the transcription line

- **WHEN** a headword has both a transcription and audio for a part of speech
- **THEN** the audio links are shown on the same line as the transcription

#### Scenario: Parts of speech are separated

- **WHEN** a card has more than one part of speech
- **THEN** each part of speech after the first is preceded by a blank line

#### Scenario: A shared audio file is shown once

- **WHEN** two parts of speech of one card reference the same audio file
- **THEN** that audio file appears once on the card
