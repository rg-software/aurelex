## Purpose

Lets a dictionary offer pronunciation recordings the source snapshot never
mentioned, by matching a card against corpora that record a word by name — a
capability each source-language profile declares and each run opts into.

## ADDED Requirements

### Requirement: A source's recordings are found by the word they record

The system SHALL offer, for a card the source snapshot leaves without audio,
recordings from a source other than the snapshot, matched to that card by the
word the recording records. The recorded word SHALL be recovered from the
recording's own name; a recording whose name yields no word SHALL NOT be
offered, and a source whose recordings cannot be matched that way SHALL NOT be
usable.

#### Scenario: A card the snapshot leaves silent gains audio

- **WHEN** a card has no recording in the source snapshot and an enabled
  additional source holds a recording of the word that card indexes
- **THEN** the card's article references that recording and the recording is
  bundled

#### Scenario: A recording whose name carries no word is not offered

- **WHEN** an additional source holds a recording whose name yields no recorded
  word
- **THEN** the recording is not matched to any card and is not bundled

### Requirement: A source is declared per language and enabled per run

A source-language profile SHALL declare which additional sources cover that
language, the language the corpus files its recordings under, and which of a
card's forms are matched against it. The system SHALL include an additional
source's recordings only when the run enables that source. A run that enables a
source the profile does not declare for that language SHALL fail with an
explanatory message rather than produce a dictionary.

#### Scenario: A declared source that is enabled contributes

- **WHEN** a run enables a source the profile declares for that language
- **THEN** that source's recordings are offered to the language's cards

#### Scenario: A source the profile does not declare is refused

- **WHEN** a run enables a source the profile does not declare for that language
- **THEN** the run fails with a message naming the source and the language, and
  no dictionary is produced

#### Scenario: A source that is not enabled contributes nothing

- **WHEN** a run enables no additional source
- **THEN** the dictionary offers exactly the recordings the snapshot supplied

### Requirement: Candidates are matched against the whole card

The system SHALL match a candidate recording against the card's headword, its
inflected forms, and its readings, comparing spellings without regard to letter
case or to the separator a corpus writes a multi-word recording with. Matching a
card's readings SHALL NOT require reading indexing to be enabled. A recording
whose word matches no card and no form of one SHALL NOT be bundled.

#### Scenario: A reading is matched

- **WHEN** an additional source records a word that is a card's reading rather
  than its headword
- **THEN** that recording is matched to the card

#### Scenario: An inflected form is matched

- **WHEN** an additional source records an inflected form of a word and the
  profile matches forms for that language
- **THEN** that recording is matched to the card for that word

#### Scenario: Case and separators do not decide a match

- **WHEN** a corpus spells a recorded word with a different letter case or a
  different separator than the card does
- **THEN** the recording is still matched to the card

#### Scenario: A recording no card wants is not bundled

- **WHEN** an additional source holds a recording whose word matches no card
- **THEN** the recording is not bundled and is not reported as a card's audio

### Requirement: Snapshot audio keeps precedence

An enabled additional source SHALL fill only the per-headword audio slots the
source snapshot's own recordings left empty, SHALL NOT displace a recording the
snapshot supplied, and the per-headword limit SHALL continue to bound the total
number of bundled files for a headword. Disabling audio SHALL suppress
additional sources as well.

#### Scenario: Only the empty slots are filled

- **WHEN** a card already has as many recordings as the per-headword limit
  allows
- **THEN** no additional source's recording is added to that card

#### Scenario: A snapshot recording is never displaced

- **WHEN** a card has a recording the snapshot supplied and a free slot
- **THEN** the additional source's recording takes the free slot and the
  snapshot's recording is kept

#### Scenario: The limit still bounds the total

- **WHEN** additional sources fill the remaining slots of a card
- **THEN** no headword has more bundled audio files than the configured limit

#### Scenario: Disabling audio suppresses additional sources

- **WHEN** the per-headword limit is set to zero and an additional source is
  enabled
- **THEN** no audio files are bundled

### Requirement: A matched recording is located and bundled like any other

A matched recording SHALL be treated as an ordinary wanted recording: located in
the local download cache or the audio archive, fetched through the existing
prefetch machinery when neither holds it, and bundled under the name its article
references. A matched recording that resolves nowhere SHALL NOT consume a slot
and SHALL be reported. Enabling an additional source and reusing an existing
bundle are mutually exclusive, and a run that does both SHALL fail with an
explanatory message rather than reuse a bundle that cannot hold the new
recordings.

#### Scenario: A cached recording is reused

- **WHEN** a matched recording is already in the local download cache
- **THEN** it is bundled without a fetch and without a change to any other
  bundled file

#### Scenario: An uncached recording is fetched on demand

- **WHEN** a matched recording is in neither the cache nor the audio archive
- **THEN** it is fetched into the cache through the same machinery a snapshot
  recording uses, and bundled

#### Scenario: A recording that resolves nowhere frees its slot

- **WHEN** a matched recording cannot be located and cannot be fetched
- **THEN** it is not bundled, the slot it would have taken is offered to the next
  candidate, and the run reports it

#### Scenario: Reusing a bundle together with a source is refused

- **WHEN** a run enables an additional source and also reuses an existing bundle
- **THEN** the run fails with a message explaining that new recordings cannot be
  added to a reused bundle, and no dictionary is produced

### Requirement: A source's index is built once and reused

The system SHALL enumerate an enabled source's recordings into an index from the
recorded word to its recordings, and SHALL cache that index together with a
fingerprint of what it was built from. It SHALL reuse a cached index whose
fingerprint matches and SHALL rebuild the index when it does not. A run whose
sources' indexes are already cached SHALL need no network to obtain them.

#### Scenario: A second run reuses the cached index

- **WHEN** a source's index is cached and a later run enables that source
- **THEN** the cached index is used and the run makes no request to list the
  source's recordings

#### Scenario: A changed fingerprint rebuilds the index

- **WHEN** the cached index's fingerprint no longer matches what it was built
  from
- **THEN** the index is rebuilt

### Requirement: A source declares its licence and per-recording credit

Each additional source SHALL declare the licence its recordings are distributed
under and where its per-recording credit is recorded, and the index SHALL hold
that declaration and the credit for each recording it offers, so any recording in
a published dictionary can be traced to its source, licence and credit.

#### Scenario: A recording carries its credit

- **WHEN** an additional source offers a recording
- **THEN** the recording is recorded with its source, that source's licence, and
  the credit the source requires for that recording

#### Scenario: A source with no per-recording credit says so

- **WHEN** a source declares a licence but requires no per-recording credit
- **THEN** the index records the licence and no credit, and the dictionary still
  names the source and its licence

### Requirement: The build reports what each source contributed

The build SHALL report, per enabled source, how many recordings it contributed
and how many cards gained audio from it, and SHALL state when a source
contributed nothing, so that a run's report accounts for the option's effect.

#### Scenario: Contributions are counted per source

- **WHEN** a run enables two sources and each contributes recordings
- **THEN** the report gives each source's contributed recordings and the number
  of cards that gained audio from it

#### Scenario: A source that matched nothing is reported as such

- **WHEN** an enabled source contributes no recordings
- **THEN** the report says so rather than omitting the source

#### Scenario: A run with no source enabled reports no contributions

- **WHEN** a run enables no additional source
- **THEN** the report states no source contributed recordings