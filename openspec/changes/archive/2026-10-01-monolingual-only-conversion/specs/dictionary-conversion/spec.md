## REMOVED Requirements

### Requirement: Language-pair selection

**Reason**: The converter builds monolingual dictionaries only. The
cross-language data it would need for a translation dictionary is too sparse and
too loosely aligned (measured in `docs/KAIKKI-CONVERSION.md`), and no
target-language selection is offered.
**Migration**: Replaced by "Language selection"; each language is built from its
own data edition, whose glosses are in that language.

### Requirement: Article content

**Reason**: Its bilingual clause promised target-language translations the
converter does not produce.
**Migration**: Replaced by the monolingual "Article content".

## ADDED Requirements

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

### Requirement: Article body

Each indexed headword article SHALL include the word's parts of speech and its
glosses, the grammatical forms of the base word, and, where the source provides
them, examples.

#### Scenario: Article content

- **WHEN** an article is rendered
- **THEN** it shows the word's parts of speech, glosses, examples where present,
  and its grammatical forms
