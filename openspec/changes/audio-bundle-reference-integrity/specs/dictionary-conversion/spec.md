## MODIFIED Requirements

### Requirement: Optional reuse of an existing resource bundle

The system SHALL provide an option to render the dictionary without rebuilding
its resource bundle, leaving the bundle already present beside the dictionary as
it is. When this option is used, the system SHALL verify that the existing bundle
contains every resource the produced dictionary references, comparing resource
names case-insensitively, because the dictionary's references and the bundle's
entries may spell the same recording differently and the consumer's filesystem
may not forgive the difference. A bundle that lacks a referenced resource, a
bundle whose reference differs from its entry only in case, and the absence of a
bundle SHALL each fail the run with a non-zero exit status rather than leaving a
broken reference silently or publishing a dictionary and a bundle that disagree.
When a referenced resource is present only under a differently-cased name, the
system SHALL add it to the bundle under the name the dictionary references
before finishing.

#### Scenario: An existing complete bundle is reused

- **WHEN** the option is given and the resource bundle beside the dictionary
  already contains every resource the rendered dictionary references
- **THEN** the dictionary is written, the resource bundle is left unchanged, and
  the run reports the reuse

#### Scenario: A referenced resource is missing from the reused bundle

- **WHEN** the option is given and the existing bundle lacks a resource the
  rendered dictionary references
- **THEN** the run reports how many referenced resources are missing and exits
  with a non-zero status without publishing the pair

#### Scenario: A reference differs from a bundle entry only in case

- **WHEN** the option is given and a resource the rendered dictionary references
  is present in the bundle under a name that differs only in letter case
- **THEN** the run copies the file into the bundle under the name the dictionary
  references, reports the repair, and exits successfully

#### Scenario: A reference matches no bundle entry under any case

- **WHEN** the option is given and a referenced resource is in the bundle neither
  under its own name nor under any case variant of it
- **THEN** the run reports the missing resources and exits with a non-zero status

#### Scenario: No bundle to reuse

- **WHEN** the option is given and there is no resource bundle beside the
  dictionary
- **THEN** the run reports that the dictionary's referenced resources are not
  present and exits with a non-zero status

#### Scenario: The bundle is rebuilt when the option is not given

- **WHEN** the option is not given
- **THEN** the resource bundle is rebuilt from the cache and archive as before

## ADDED Requirements

### Requirement: A finished build's references all resolve

The system SHALL verify, after writing the dictionary and its resource bundle,
that every audio-extension resource the written dictionary references is present
in the written bundle, and SHALL fail the run with a non-zero exit status naming
the unresolved references when any is missing. This check SHALL apply to every
build, whatever path wrote the bundle, and SHALL be runnable on its own against
an existing dictionary and bundle pair so a published pair can be audited without
re-rendering it. Links that are not audio resources, such as the sense-marker
icons, SHALL be checked by their own rules and SHALL NOT be reported by this
check.

#### Scenario: A build whose references all resolve

- **WHEN** a build finishes and every audio link in the written dictionary names
  an entry of the written bundle
- **THEN** the run reports the verified count and exits successfully

#### Scenario: A build that leaves an audio reference unresolved

- **WHEN** a build finishes and an audio link in the written dictionary names no
  entry of the written bundle
- **THEN** the run lists the unresolved names, including how many differ from a
  bundled entry only in case, and exits with a non-zero status

#### Scenario: The check is run against an existing pair

- **WHEN** the check is run against a dictionary and bundle that were written by
  an earlier run
- **THEN** it reports the same unresolved references and changes neither file

#### Scenario: Sense-marker icons are not reported

- **WHEN** a dictionary references only the sense-marker icons and no audio
- **THEN** the check reports every icon present and no unresolved reference

#### Scenario: A dictionary with no bundle beside it

- **WHEN** the check is run and no resource bundle sits beside the dictionary
- **THEN** it reports that the bundle is missing and exits with a non-zero status
