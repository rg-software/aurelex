## MODIFIED Requirements

### Requirement: Source-language profiles

The system SHALL carry a profile for each supported source language, describing
its grammatical form vocabulary and short labels, the display labels for its
parts of speech, the tags that disqualify a form, the pronunciation fields to
prefer, and how its sense tags are presented (their abbreviations, and the ones
that are not shown). A profile SHALL also declare whether the language has
pronunciation recordings at all; a language without them SHALL NOT cause the
audio archive to be fetched, in the build or in the pre-fetcher. A source
language without a profile SHALL fall back to a permissive default and SHALL
report that it is doing so. English, German, Japanese and Russian SHALL have
profiles.

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

### Requirement: Example qualification

An example SHALL be kept for a sense only when it contains the headword or one of
the base word's listed forms. A cross-reference bookkeeping example SHALL NOT be
kept. An archaic example (Early Modern or Middle English spelling or inflection)
SHALL NOT be kept for a sense that is not marked obsolete, dated or archaic; for
a sense that is so marked, an archaic example SHALL be shown when no other
qualifying example exists, so such a sense is illustrated rather than left bare,
and a modern-readable example SHALL be preferred when one exists. An example
longer than a fixed bound SHALL be shortened at a word boundary to keep the part
that shows the headword in use: the sentence containing the headword, or, when
that sentence too exceeds the bound, a window around the headword. In a language
written without word spaces, the headword SHALL be matched as a substring of the
example, and a sentence SHALL end at that language's own sentence punctuation as
well as at `.`.

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

#### Scenario: An over-long example keeps the headword

- **WHEN** a qualifying example exceeds the length bound and the headword appears
  past the bound
- **THEN** the shown text still contains the headword, taken from the sentence
  that carries it (or a window around it), and an ellipsis marks any cut edge

#### Scenario: An over-long example is shortened

- **WHEN** a qualifying example exceeds the length bound
- **THEN** it is cut at a word boundary that fits the bound

#### Scenario: A CJK headword is matched without word boundaries

- **WHEN** an example in a language written without word spaces contains the
  headword in the middle of a clause
- **THEN** the example qualifies, and the headword is located inside the clause

#### Scenario: A CJK example is bounded by its own full stop

- **WHEN** an example in a language written without word spaces runs past the
  bound and the headword's sentence ends with that language's full stop
- **THEN** the shown text is that sentence, and its leading clauses are dropped
