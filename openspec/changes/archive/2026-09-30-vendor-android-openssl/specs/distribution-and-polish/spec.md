## ADDED Requirements

### Requirement: Self-contained release builds
The system SHALL produce every distributable artifact from a checkout that is
complete on its own: each native library the artifact loads at run time SHALL be
tracked in version control and therefore present in a fresh checkout, so that no
release depends on state existing only on a maintainer's machine. Where a
vendored run-time library is absent from the checkout, the build SHALL fail in
every configuration rather than continue and produce an artifact with the library
missing. The system SHALL verify that the vendored libraries are present in the
packaged artifact before that artifact is published, and SHALL record the
upstream source and per-file integrity digests of the vendored binaries so the
exact bits that ship are traceable to a specific upstream revision.

#### Scenario: Fresh checkout builds a complete artifact
- **WHEN** a clean checkout is used to build a release artifact
- **THEN** the build succeeds and the artifact contains the vendored run-time
  libraries the app loads at run time, without retrieving them from any
  external source during the build

#### Scenario: Missing vendored library fails the build
- **WHEN** a build is configured for an ABI whose vendored run-time libraries are
  absent from the checkout
- **THEN** the build fails with an error naming the missing path, in every
  configuration, and no artifact is produced

#### Scenario: Packaged artifact is verified before publication
- **WHEN** a release artifact has been packaged
- **THEN** the presence of the vendored run-time libraries in the packaged
  artifact is checked and the build fails before publication if any is absent

#### Scenario: Vendored binaries are traceable to an upstream revision
- **WHEN** a maintainer inspects the documentation for the vendored libraries
- **THEN** the upstream project, the exact upstream revision the binaries were
  taken from, and a digest for each committed binary file are recorded

#### Scenario: A run-time library missing from the artifact is a build failure,
  not a user-visible runtime error
- **WHEN** a change would cause a release artifact to omit a library the app
  loads at run time
- **THEN** the omission is detected by the build or its packaging check, and is
  never discovered by a user as a feature that fails at run time
