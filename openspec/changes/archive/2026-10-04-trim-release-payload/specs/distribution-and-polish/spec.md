## MODIFIED Requirements

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

A packaged artifact SHALL contain only the native libraries the app can reach at
run time — directly linked, imported as a module, or named as a platform or
run-time plugin — and SHALL NOT carry libraries it cannot reach, including
development, authoring-tool and unused-style libraries. The set of libraries an
artifact needs SHALL be derived from what the app actually links and imports
rather than maintained by hand, so that adding a dependency widens the payload
and upgrading the runtime kit does not silently widen it by accident. The
libraries an artifact's run-time configuration names SHALL be packaged in every
place the artifact looks for them, so filtering cannot leave a reachable library
present in one location and absent from another.

The total size of the packaged native payload SHALL be checked against a recorded
budget before the artifact is published, and a payload that exceeds the budget —
or that carries a library the app cannot reach — SHALL fail the build rather than
be published.

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

#### Scenario: Unreachable libraries are not packaged
- **WHEN** a release artifact is packaged
- **THEN** it contains no native library the app cannot reach at run time, and in
  particular no development, authoring-tool, or unused-style library, regardless
  of those being present in the runtime kit the build staged from

#### Scenario: The packaged set follows what the app uses
- **WHEN** the app gains a native dependency or a module import that is resolved
  from the runtime kit
- **THEN** the next artifact includes the libraries that dependency needs,
  without requiring the set of packaged libraries to be updated by hand

#### Scenario: A reachable library is packaged everywhere it is looked for
- **WHEN** a release artifact is packaged with a filtered library set
- **THEN** every library the run-time configuration can request is present in
  each location the artifact searches for libraries, and the app starts and
  renders its interface normally

#### Scenario: An over-budget payload fails the build
- **WHEN** a release artifact's native payload exceeds the recorded size budget,
  or contains a library the app cannot reach
- **THEN** the build fails before publication, naming the offending library or the
  measured size, instead of publishing the artifact