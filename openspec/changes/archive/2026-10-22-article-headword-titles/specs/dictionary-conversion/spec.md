## MODIFIED Requirements

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
first part of speech that references it. When a card is emitted under more than
one headword (alias headwords from opt-in reading or inflection indexing), the
card SHALL open with its primary (base-form) headword as a title line above
everything else, so an article reached through an alias lookup says which word
it defines. A card emitted under a single headword SHALL carry no title line.

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

#### Scenario: An alias card opens with its primary headword

- **WHEN** a card is indexed under its base headword plus alias headwords
  (readings, inflected forms)
- **THEN** the article opens with the base headword as a title line above the
  readings, transcriptions, parts of speech and everything else

#### Scenario: A single-headword card carries no title

- **WHEN** a card is indexed under one headword only
- **THEN** the article carries no title line and renders exactly as without one
