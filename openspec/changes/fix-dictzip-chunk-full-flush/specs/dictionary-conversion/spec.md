## MODIFIED Requirements

### Requirement: Import-ready, deterministic packaging

The output SHALL be a single dictzip-compressed DSL dictionary file (`.dsl.dz`).
The system SHALL NOT emit an uncompressed `.dsl` file as part of its normal
output. The compressed file SHALL be readable by seeking: every chunk recorded in
its chunk index SHALL be independently inflatable, without relying on data from
any other chunk, so a reader can seek to a chunk and inflate just that chunk.
Referenced audio SHALL be bundled as a sibling resource that the app's
DSL resource resolution finds, either inside a single resource archive or in a
resource directory, and the archive form SHALL be used by default to avoid a
large number of loose files. Rebuilding from the same snapshot and options SHALL
produce byte-identical output.

#### Scenario: Compressed dictionary file is emitted
- **WHEN** the tool produces a dictionary
- **THEN** the dictionary is a dictzip-compressed `.dsl.dz` file and no
  uncompressed `.dsl` file is emitted

#### Scenario: Every chunk can be read on its own
- **WHEN** a produced dictionary's uncompressed content is larger than one chunk
- **THEN** each chunk in its chunk index inflates independently, so a reader that
  seeks to any chunk reads it without error

#### Scenario: Audio is bundled as a resource archive
- **WHEN** the tool bundles audio with the default packaging
- **THEN** the referenced audio is placed in a single sibling resource archive
  that the app resolves when the dictionary is imported

#### Scenario: Audio can be bundled as a resource directory
- **WHEN** the tool is asked to bundle audio as loose files
- **THEN** the referenced audio is placed in a sibling resource directory that
  the app resolves when the dictionary is imported

#### Scenario: Deterministic rebuild
- **WHEN** the tool is run twice with the same snapshot and options
- **THEN** the two outputs are byte-identical
