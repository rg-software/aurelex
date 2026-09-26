## MODIFIED Requirements

### Requirement: Signed release artifacts
The system SHALL produce a signed release AAB and APK from CI using a signing
keystore supplied via CI secrets (never committed to the repository), and SHALL
derive versionCode/versionName from the release tag rather than a fixed value.
Release publication SHALL be restricted to release tags whose version components
each fit the deterministic encoding, so tag-derived versionCodes cannot collide.

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

### Requirement: Google Play signing
The system SHALL distribute to Google Play under Play App Signing: an upload
key signs the AAB we upload, while Google's app-signing key signs the APKs Play
delivers. The distinct roles of the upload key and the app-signing key SHALL be
documented. On each release tag, the system SHALL automatically publish the
signed AAB to the app's internal testing track via the Google Play Developer
API, authenticated by a service account whose credential is a CI secret.

#### Scenario: Play distributes with its app-signing key
- **WHEN** a signed AAB is uploaded to Play Console
- **THEN** Play App Signing re-signs it with Google's app-signing key before
  users install it

#### Scenario: Upload key is recoverable separately
- **WHEN** the developer loses the upload key
- **THEN** it can be reset via Play Console without re-keying delivered apps

#### Scenario: Tagged release publishes to internal testing
- **WHEN** a well-formed release tag is pushed and the signed AAB is built
- **THEN** CI uploads the AAB to the internal testing track via the Play
  Developer API without a manual Play Console step

#### Scenario: Publish credential comes only from a secret
- **WHEN** CI authenticates to the Play Developer API
- **THEN** the service account credential is read only from CI secrets and never
  appears in the repository or release artifacts

#### Scenario: Publish failure does not lose the build
- **WHEN** the Play publish step fails (missing or rejected credential, API
  error)
- **THEN** the signed APK and AAB are still attached to the GitHub release and
  the failure is surfaced in the workflow result
