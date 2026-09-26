# distribution-and-polish Specification

## Purpose

Lets a user install and recognize Aurelex by shipping signed, versioned release
artifacts through Google Play and F-Droid (and sideload), an app icon, and
first-run onboarding with helpful empty states.
## Requirements
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

### Requirement: F-Droid signing
The system SHALL provide F-Droid with a stable signing strategy so its
source-built APKs carry our signature: either a shared signing keystore or a
reproducible build verified to match our published APK. The chosen strategy
SHALL be documented.

#### Scenario: F-Droid signs with our key
- **WHEN** F-Droid builds the app from source for a release
- **THEN** the APK it publishes matches the stored signing key fingerprint so
  updates remain compatible

#### Scenario: Signatures differ per channel by design
- **WHEN** the app is published on both Google Play and F-Droid
- **THEN** each channel's signature is independent (Play uses Google's
  app-signing key; F-Droid uses ours) and cross-store updates are not required

### Requirement: App icon
The system SHALL ship a proper adaptive launcher icon and SHALL use it in the
app notifications and the home-screen widget.

#### Scenario: Launcher shows the app icon
- **WHEN** the user looks at the launcher
- **THEN** Aurelex shows its adaptive icon instead of a default placeholder

#### Scenario: Notification and widget use the icon
- **WHEN** the engine notification or home-screen widget is rendered
- **THEN** it uses the same app icon

### Requirement: First-run onboarding
The system SHALL guide a new user through first steps on first launch and SHALL
show helpful guidance when the app has no dictionaries yet. On first launch the
app SHALL land on the Dictionaries tab (which has no article WebView), show an
onboarding card teaching how to add dictionaries, and SHALL NOT pop the onscreen
keyboard. Once onboarding is complete (no onboarding screen shown), the app SHALL
start on the Search tab on every launch.

#### Scenario: First launch shows onboarding on the Dictionaries tab
- **WHEN** the app is launched for the first time
- **THEN** it lands on the Dictionaries tab, shows an onboarding card explaining
  how to add dictionaries, and the onscreen keyboard is not shown

#### Scenario: Onboarding is dismissed
- **WHEN** the user taps "Get started" on the onboarding card
- **THEN** the card disappears, the keyboard is not shown, and the app switches
  to the Search tab

#### Scenario: Subsequent launches start on Search
- **WHEN** the user opens the app after onboarding is complete
- **THEN** the app starts on the Search tab (no onboarding screen)

#### Scenario: Empty search state
- **WHEN** the user opens search with no dictionaries loaded
- **THEN** the app explains (via onboarding guidance or a non-blank empty state)
  that dictionaries must be added first, instead of showing a blank screen

