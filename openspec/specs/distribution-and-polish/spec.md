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
  it ships, and the libraries in the installable part of the bundle are stripped

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
app notifications and the Quick-Settings tile.

#### Scenario: Launcher shows the app icon
- **WHEN** the user looks at the launcher
- **THEN** Aurelex shows its adaptive icon instead of a default placeholder

#### Scenario: Notification and tile use the icon
- **WHEN** the engine notification or the Quick-Settings tile is rendered
- **THEN** it uses the same app icon

### Requirement: First-run onboarding
The system SHALL guide a new user through first steps on first launch and SHALL
show helpful guidance when the app has no dictionaries yet. On first launch the
app SHALL land on the Dictionaries tab (which has no article WebView), show an
onboarding card teaching how to add dictionaries, and SHALL NOT pop the onscreen
keyboard. When onboarding is dismissed the app SHALL leave the user on the
Dictionaries tab, so the add-dictionary controls the card described are
immediately available. Once onboarding is complete (no onboarding screen shown),
every later launch SHALL start on the Search tab.

#### Scenario: First launch shows onboarding on the Dictionaries tab
- **WHEN** the app is launched for the first time
- **THEN** it lands on the Dictionaries tab, shows an onboarding card explaining
  how to add dictionaries, and the onscreen keyboard is not shown

#### Scenario: Onboarding is dismissed
- **WHEN** the user taps "Get started" on the onboarding card
- **THEN** the card disappears, the keyboard is not shown, and the app is on the
  Dictionaries tab with the add-dictionary controls reachable without navigating

#### Scenario: Subsequent launches start on Search
- **WHEN** the user opens the app after onboarding is complete
- **THEN** the app starts on the Search tab (no onboarding screen)

#### Scenario: Empty search state
- **WHEN** the user opens search with no dictionaries loaded
- **THEN** the app explains (via onboarding guidance or a non-blank empty state)
  that dictionaries must be added first, instead of showing a blank screen

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

### Requirement: Launch starting window matches the app background

The system SHALL show a starting window on app launch — the platform splash screen where one
exists, the legacy starting window on older releases — and that window's background SHALL be the
same color the app itself paints its background in, for the theme the device is currently in. The
starting window SHALL show the app's launcher icon, and SHALL NOT be backed by a separate
splash-screen drawable. The color of the first frame the app renders SHALL be that same background,
so no frame of a different brightness appears between the starting window and the running app.

The starting window is drawn by the operating system before the app has run, so it can only
reflect the **system** theme. A user who has forced the app to a theme the system is not in
SHALL still start from the starting window of the system theme; the app then switches to the
forced theme once it is running. That handoff SHALL NOT introduce a bright or blank frame.

#### Scenario: Dark system theme starts dark
- **WHEN** the user launches the app on a device whose system theme is dark, and the app is following the system theme
- **THEN** the starting window's background is the app's dark background, not white

#### Scenario: Light system theme starts light
- **WHEN** the user launches the app on a device whose system theme is light
- **THEN** the starting window's background is the app's light background

#### Scenario: The first app frame matches the starting window
- **WHEN** the user launches the app on a device whose system theme is dark, and the app is following the system theme
- **THEN** the app's first rendered frame uses that same dark background, with no intervening white or blank frame

#### Scenario: The starting window shows the app icon
- **WHEN** the starting window is displayed
- **THEN** it shows the app's launcher icon rather than a separate splash artwork

#### Scenario: Older Android releases use the same background
- **WHEN** the app is launched on a release that predates the platform splash screen
- **THEN** the legacy starting window uses the same background as the app, for the system theme in effect

#### Scenario: A forced theme overrides the system theme after launch
- **WHEN** the system theme is dark but the user has forced the app to the light theme, and the app is launched
- **THEN** the starting window uses the dark system theme's background, and the app comes up in the forced light theme without a blank or mismatched frame

#### Scenario: The system theme change is followed on the next launch
- **WHEN** the user changes the system theme and then launches the app again
- **THEN** the starting window uses the new system theme's background

### Requirement: Store listing assets are validated before publication

The system SHALL validate the versioned store listing assets — the listing icon,
the feature graphic and the phone screenshots — against the constraints the target
store enforces, and SHALL fail the check when any of them is violated, so that a
malformed or duplicated asset set is caught by the repository rather than by the
store rejecting an upload.

The validation SHALL cover, for the phone-screenshot gallery: that it is within
the store's per-language screenshot limit; that every screenshot is within the
store's minimum and maximum pixel bounds on each side; that every screenshot has
an aspect ratio the store accepts; that no two screenshots share identical
content; and that the gallery's ordering prefixes are unique and contiguous from
one, so the published order is the order the filenames declare. For the listing
icon and the feature graphic it SHALL check that each is present at the
dimensions the store requires.

The check SHALL NOT require the assets to be regenerated in order to run, so that
it is usable on a machine without the image tooling the converter needs. It SHALL
report every violation it finds rather than only the first.

The store listing copy SHALL state the same constraints in prose, so the numbers
a maintainer needs to respect by hand are the numbers the check enforces.

#### Scenario: A gallery within the store's limits passes

- **WHEN** the check runs against a gallery whose screenshot count is within the
  store's limit and whose files satisfy every dimension, ratio, uniqueness and
  ordering rule
- **THEN** the check succeeds

#### Scenario: Too many screenshots fails

- **WHEN** the gallery contains more screenshots than the store accepts for one
  language
- **THEN** the check fails and names the limit and the actual count

#### Scenario: A wrongly sized screenshot fails

- **WHEN** a screenshot falls outside the store's minimum or maximum pixel bounds
  on either side, or has an aspect ratio the store does not accept
- **THEN** the check fails and names the file, its dimensions and the bound or
  ratio that was violated

#### Scenario: Duplicate screenshot content fails

- **WHEN** two screenshots in the gallery have identical bytes, as happens when a
  renamed capture leaves the previous file behind
- **THEN** the check fails and names both files, so the stale one can be removed

#### Scenario: Ambiguous gallery order fails

- **WHEN** two screenshots share an ordering prefix, or the prefixes are not
  contiguous from one
- **THEN** the check fails, because the published gallery order would not be the
  order the filenames claim

#### Scenario: A missing or wrongly sized listing icon fails

- **WHEN** the listing icon or the feature graphic is absent, or is not at the
  dimensions the store requires
- **THEN** the check fails and names the missing or wrongly sized asset

#### Scenario: Every violation is reported at once

- **WHEN** the gallery violates more than one rule
- **THEN** the check reports each violation, not only the first one found

#### Scenario: The documented constraints match the enforced ones

- **WHEN** a maintainer reads the constraints stated beside the listing copy
- **THEN** the limits, bounds and ratios stated there are the ones the check
  enforces, so hand-made assets and checked assets are held to the same rule

