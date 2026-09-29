## MODIFIED Requirements

### Requirement: Settings persistence
The system SHALL persist user preferences (favorites, history, the app theme mode, and the article zoom level) across app restarts. The theme mode SHALL be persisted as one of three settings — follow the system, force light, or force dark — and the stored setting SHALL survive a restart unchanged rather than being resolved to the theme that happened to be showing when the app closed.

#### Scenario: Preferences survive restart
- **WHEN** the user changes a preference (e.g. theme mode, article zoom) or modifies favorites/history and then restarts the app
- **THEN** the preferences and lists retain the user's changes

#### Scenario: Zoom level survives restart
- **WHEN** the user sets an article zoom level and restarts the app
- **THEN** articles render at the stored zoom level without the user re-setting it

#### Scenario: Theme mode survives restart as the stored setting
- **WHEN** the user sets the theme to follow the system, to force light, or to force dark, and then restarts the app while the system theme is unchanged
- **THEN** the app comes up in that same theme mode, not in whichever mode the system theme happens to imply

## ADDED Requirements

### Requirement: Theme mode has three settings

The system SHALL offer the user three theme modes — follow the system, force light, and
force dark — and SHALL let the user switch between them from a single control in the app's
bottom dock. In follow-the-system mode the app's theme SHALL track the system theme,
including following it when the system theme changes while the app is running. In force-light
and force-dark mode the app's theme SHALL remain that mode regardless of the system theme,
including while the system theme changes.

Every tap of the control SHALL select a different mode from the one currently stored, and
SHALL leave the control showing that newly selected mode. A cycle over three modes cannot
also change the rendered appearance on every tap, because the appearance has only two
values: the one appearance-preserving step in each cycle is the one that returns control to
the system while the system already shows what was just left. That step still changes the
stored mode and the control's own appearance, so the control is never inert.

#### Scenario: Following the system tracks a live system change
- **WHEN** the app is in follow-the-system mode and the system theme changes from light to dark
- **THEN** the app's theme changes to dark without a restart or a re-lookup of the open article

#### Scenario: A forced theme ignores the system
- **WHEN** the app is in force-light mode and the system theme changes to dark
- **THEN** the app stays in its light theme

#### Scenario: Every tap changes the mode and the control's shown target
- **WHEN** the user taps the theme control from any mode, with the system theme set to either light or dark
- **THEN** the app's stored mode is the next mode in the cycle, and the control's icon and accessible name show that newly selected mode as the target of the following tap
- **AND** the app's appearance is that mode's appearance, except where the selected mode resolves to the appearance the system is already showing

#### Scenario: The mode is restored across a restart
- **WHEN** the user sets any of the three modes and restarts the app
- **THEN** the app opens in that same mode, with the control already showing that mode as its current state

#### Scenario: An unrecognized stored mode falls back to following the system
- **WHEN** the app starts with a stored theme mode that is not one of the three recognized settings
- **THEN** the app runs in follow-the-system mode rather than failing to start

### Requirement: The theme control shows the mode the next tap selects

The theme control SHALL display an icon and an accessibility name that both describe the
theme mode the **next** tap will select, not the mode currently in effect. The control SHALL
show the sun glyph when the next tap selects the light theme, the moon glyph when the next
tap selects the dark theme, and a distinct follow-the-system glyph when the next tap returns
the theme to following the system. Because the two explicit modes and follow-the-system are
distinguished this way, the control SHALL never show the same icon-and-name pair for two
different modes.

The accessibility name SHALL follow the same target convention, announcing "Dark mode"
when the next tap selects dark, "Light mode" when it selects light, and "Follow system
theme" when it returns to following the system.

#### Scenario: Control announces the theme the next tap selects
- **WHEN** the next tap would select the dark theme, which is the case whenever the light theme is stored
- **THEN** the control shows the moon glyph and announces "Dark mode"

#### Scenario: Auto advertises that a tap pins an explicit theme
- **WHEN** the app is following the system, so the next tap selects the light theme
- **THEN** the control shows the sun glyph and announces "Light mode"

#### Scenario: Dark advertises that a tap returns control to the system
- **WHEN** the app is in the dark mode, so the next tap returns the theme to following the system
- **THEN** the control shows the follow-the-system glyph and announces "Follow system theme"

#### Scenario: Each mode has a distinct control appearance
- **WHEN** the control is inspected in each of the three modes
- **THEN** the follow-the-system mode is distinguishable from both explicit modes, and the two explicit modes are distinguishable from each other

### Requirement: The resolved theme drives all app appearance

Which theme is in effect SHALL be derived from the theme mode and the system theme, and that
single resolved theme SHALL drive every part of the app's appearance together: the app
chrome and controls, the system status- and navigation-bar icon contrast, the theme
dictionaries render articles in, and the article currently on screen. Switching modes SHALL
take effect on the article already displayed without re-running the lookup, and a dictionary
article SHALL be readable in both themes.

#### Scenario: All appearance follows the resolved theme
- **WHEN** the resolved theme changes, whether because the mode changed or because the system theme did
- **THEN** the app chrome, the system bar icon contrast, the dictionary rendering theme, and the open article all change to that theme together

#### Scenario: The open article switches in place
- **WHEN** the resolved theme changes while an article is displayed
- **THEN** the displayed article changes to the new theme in place without losing the looked-up word or returning to an empty article

#### Scenario: Articles are readable in either theme
- **WHEN** an article is rendered in the light theme and again in the dark theme
- **THEN** the entry's text is legible against its background in both
