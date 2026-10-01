## ADDED Requirements

### Requirement: Source-language profiles

The system SHALL carry a profile for each supported source language, describing
its grammatical form vocabulary and short labels, the tags that disqualify a
form, the pronunciation fields to prefer, and how its sense tags are presented.
A source language without a profile SHALL fall back to a permissive default and
SHALL report that it is doing so. English, German, Japanese and Russian SHALL
have profiles.

#### Scenario: A language with a profile needs no fallback

- **WHEN** the tool builds with a source language that has a profile
- **THEN** it does not report a missing-profile fallback

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
- **THEN** no missing-profile fallback is reported, and Russian forms and sense
  tags are labelled with the Russian profile's terms

#### Scenario: A language without a profile falls back and reports it

- **WHEN** the tool builds with a source language that has no profile
- **THEN** it reports that it is using a permissive default
