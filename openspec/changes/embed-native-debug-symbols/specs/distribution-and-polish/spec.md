## MODIFIED Requirements

### Requirement: Signed release artifacts
The system SHALL produce a signed release AAB and APK from CI using a signing
keystore supplied via CI secrets (never committed to the repository), and SHALL
derive versionCode/versionName from the release tag rather than a fixed value.
Release publication SHALL be restricted to release tags whose version components
each fit the deterministic encoding, so tag-derived versionCodes cannot collide.

The release AAB SHALL carry native debug symbols for every ABI it ships, so that a
native crash reported through Google Play can be symbolicated; the shipped
binaries in the artifact itself SHALL remain stripped. The release pipeline SHALL
verify that the symbols are present before the artifact is published, and SHALL
fail the release when they are not. The symbols SHALL be published alongside the
artifacts, and the path for getting them to Google Play — which accepts them
through its own console rather than through the publishing API — SHALL be
documented.

#### Scenario: Tag push produces signed artifacts
- **WHEN** a release tag is pushed
- **THEN** CI builds a signed AAB and a signed APK and attaches them to the
  release

#### Scenario: Version reflects the tag
- **WHEN** a release tagged `vX.Y.Z` is built
- **THEN** the artifact reports versionName `X.Y.Z` and a monotonically
  increasing versionCode derived from the tag

#### Scenario: Keystore never leaks
- **WHEN** CI signs a release
- **THEN** the keystore contents are read only from CI secrets and never appear
  in the repository or release artifacts

#### Scenario: Non-release refs are never published
- **WHEN** the release workflow runs for a non-release ref (a master branch push
  or a manual dry-run dispatch)
- **THEN** it produces artifacts without publishing to any store

#### Scenario: Malformed or colliding tag is rejected
- **WHEN** a pushed tag is not a well-formed `vX.Y.Z` release tag, or a version
  component is `>= 100`
- **THEN** the release fails before building or publishing rather than emitting a
  colliding versionCode

#### Scenario: Release AAB carries native debug symbols
- **WHEN** a release AAB is built
- **THEN** it contains a native debug symbols entry for each ABI whose libraries
  it ships, and the libraries in the installable part of the bundle remain
  stripped

#### Scenario: A symbol-less artifact fails the release
- **WHEN** the built release AAB does not contain the native debug symbols for a
  shipped ABI
- **THEN** the release fails before publication instead of publishing an artifact
  whose native crashes cannot be symbolicated

#### Scenario: Symbols are published with the release
- **WHEN** a release is published
- **THEN** the native debug symbols for the shipped ABI are attached to the same
  release as the AAB and APK, and the documented upload path identifies which
  artifact and ABI they belong to

#### Scenario: Symbols match the published version
- **WHEN** a maintainer uploads the native debug symbols to Google Play
- **THEN** the symbols identify the same versionCode and ABI as the AAB they were
  built with, so a reported native crash resolves to the shipped code