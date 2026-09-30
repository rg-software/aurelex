## ADDED Requirements

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
