## ADDED Requirements

### Requirement: Opt-in reading indexing

For a source language whose profile declares readings, the system SHALL provide an
opt-in mode that indexes each card's readings as additional headwords, so a
lookup of the word's reading resolves to the word's article. A reading SHALL be
indexed in hiragana, the form a kana lookup is typed in, with the source's
separators removed. The system SHALL state that enabling this mode adds those
readings to the headword suggestion list. Readings SHALL NOT be indexed unless
the mode is enabled.

#### Scenario: A reading lookup resolves to the word's article

- **WHEN** reading indexing is enabled and the user looks up a word's reading
- **THEN** that word's article is returned

#### Scenario: Readings are not indexed by default

- **WHEN** reading indexing is not enabled
- **THEN** a card's readings are not indexed as headwords, and only the word
  itself is

#### Scenario: A katakana reading is indexed in hiragana

- **WHEN** a reading the source writes in katakana is indexed
- **THEN** it is indexed in its hiragana form, so a hiragana lookup reaches it

#### Scenario: A language without readings is unaffected

- **WHEN** reading indexing is enabled for a language whose profile declares no
  readings
- **THEN** no extra headwords are indexed
