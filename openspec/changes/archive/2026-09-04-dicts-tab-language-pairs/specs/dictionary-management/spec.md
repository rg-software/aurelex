## ADDED Requirements

### Requirement: Dictionary display metadata
The system SHALL show each dictionary in the Dicts list with its source/target
language pair and an approximate size, instead of its raw file path, so the
list is readable without exposing storage details. When a dictionary is still
being indexed and its size is not yet known, the size SHALL be omitted (shown
once known). When a source or target language is not known, it SHALL be shown
as `?`.

#### Scenario: Row shows language pair and size
- **WHEN** the user opens the Dicts tab
- **THEN** each dictionary row shows its name, then `Source/Target` and an
  approximate size (e.g. `English/Russian · 145 MB`), and never the file path

#### Scenario: Unknown language pair
- **WHEN** a dictionary's source or target language is not known
- **THEN** the unknown side is displayed as `?` (e.g. `English/? · 12 MB`)

#### Scenario: Size hidden while indexing
- **WHEN** a dictionary is still being full-text indexed and its size is unknown
- **THEN** the row shows the language pair without the size, and the size appears
  once indexing finishes and the size is known

### Requirement: By-Pair grouped dictionary list
The system SHALL let the user toggle a "By Pair" grouping on the Dicts tab. When
off, dictionaries are sorted alphabetically by name. When on, dictionaries are
grouped under color-highlighted caption rows, one per source/target language
pair, sorted alphabetically by pair; within each pair the dictionaries are
sorted alphabetically by name.

#### Scenario: Toggle off shows flat alphabetical list
- **WHEN** "By Pair" is off
- **THEN** dictionaries are listed in one flat list sorted alphabetically by name

#### Scenario: Toggle on groups by language pair
- **WHEN** "By Pair" is on
- **THEN** dictionaries are grouped under caption rows labeled by their
  source/target pair, pairs are sorted alphabetically, and dictionaries within a
  pair are sorted alphabetically by name

### Requirement: Batch and per-pair dictionary removal
The system SHALL let the user remove a whole language-pair group at once from a
pair caption row, and (as a lighter convenience) remove several selected
dictionaries at once via a "RemoveSelected" control. Both reuse the permanent
removal behaviour (staged files + indexes deleted).

#### Scenario: Remove a language pair
- **WHEN** the user taps Remove on a pair caption row
- **THEN** every dictionary having that source/target pair is permanently removed
  and disappears from the list, lookups, groups, and full-text search

#### Scenario: Multi-select and RemoveSelected
- **WHEN** the user taps dictionary rows to select them (at least one) and then
  taps RemoveSelected
- **THEN** all selected dictionaries are permanently removed and the selection is
  cleared

#### Scenario: RemoveSelected is disabled with no selection
- **WHEN** no dictionary rows are selected
- **THEN** the RemoveSelected button is disabled; it becomes enabled once at
  least one dictionary is selected