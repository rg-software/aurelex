## MODIFIED Requirements

### Requirement: Dictionary display metadata
The system SHALL show each dictionary in the Dicts list with its source/target
language pair and an approximate size, instead of its raw file path, so the
list is readable without exposing storage details. Language names SHALL be shown
in the app's active language when the app knows the language, falling back to the
name in the dictionary's metadata. When a dictionary is still being indexed and
its size is not yet known, the size SHALL be omitted (shown once known). When a
source or target language is not known, it SHALL be shown as `?`.

#### Scenario: Row shows language pair and size
- **WHEN** the user opens the Dicts tab
- **THEN** each dictionary row shows its name, then `Source/Target` and an
  approximate size (e.g. `English/Russian · 145 MB`), and never the file path

#### Scenario: Language names follow the app's language
- **WHEN** the app's active language is Russian and a dictionary's metadata names
  its language in English
- **THEN** the row and the By-Pair captions show that language's Russian name

#### Scenario: Unknown language pair
- **WHEN** a dictionary's source or target language is not known
- **THEN** the unknown side is displayed as `?` (e.g. `English/? · 12 MB`)

#### Scenario: Size hidden while indexing
- **WHEN** a dictionary is still being full-text indexed and its size is unknown
- **THEN** the row shows the language pair without the size, and the size appears
  once indexing finishes and the size is known
