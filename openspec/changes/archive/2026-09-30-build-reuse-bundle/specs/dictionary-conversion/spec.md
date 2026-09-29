## ADDED Requirements

### Requirement: Optional reuse of an existing resource bundle

The system SHALL provide an option to render the dictionary without rebuilding
its resource bundle, leaving the bundle already present beside the dictionary as
it is. When this option is used, the system SHALL verify that the existing bundle
contains every resource the produced dictionary references and SHALL report any
referenced resource that the bundle lacks, or the absence of a bundle, rather
than leaving a broken reference silently.

#### Scenario: An existing complete bundle is reused

- **WHEN** the option is given and the resource bundle beside the dictionary
  already contains every resource the rendered dictionary references
- **THEN** the dictionary is written, the resource bundle is left unchanged, and
  the run reports the reuse

#### Scenario: A referenced resource is missing from the reused bundle

- **WHEN** the option is given and the existing bundle lacks a resource the
  rendered dictionary references
- **THEN** the run warns and states how many referenced resources are missing

#### Scenario: No bundle to reuse

- **WHEN** the option is given and there is no resource bundle beside the
  dictionary
- **THEN** the run warns that the dictionary's referenced resources are not
  present

#### Scenario: The bundle is rebuilt when the option is not given

- **WHEN** the option is not given
- **THEN** the resource bundle is rebuilt from the cache and archive as before
