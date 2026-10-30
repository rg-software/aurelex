# Spec Delta

## ADDED Requirements

### Requirement: DSL compression-variant deduplication
When a same-named group consists solely of dictionaries that are the same DSL
dictionary stored once plain (`.dsl`) and once compressed (`.dsl.dz`), with
matching companion files, the system SHALL treat them as identical: collapse
them to a single dictionary, keeping the compressed (`.dsl.dz`) copy and
deleting the redundant plain copy and its storage, without asking. The collapse
SHALL be reported informationally in the import-results surface (reason
`dslCompressionVariant`) so the user knows a redundant copy was removed; it
SHALL NOT be reported as a name clash requiring manual removal.

#### Scenario: A DSL and its compressed sibling collapse automatically
- **GIVEN** a folder contains both `foo.dsl` and `foo.dsl.dz` for the same
  dictionary (matching companions)
- **WHEN** a scan runs
- **THEN** only the compressed copy remains, the plain copy and its storage
  are deleted, and the import-results surface reports an informational
  `dslCompressionVariant` row rather than a name clash

#### Scenario: The compressed copy is the survivor
- **GIVEN** a same-named group contains a plain (`.dsl`) and a compressed
  (`.dsl.dz`) copy
- **WHEN** the group is collapsed
- **THEN** the compressed copy is the one retained, and its position, group
  membership and index are preserved