# usability-utilities Specification

## Purpose

Adds everyday conveniences that make Aurelex useful as a daily dictionary: looking up words from other apps or the clipboard, and browsing recent lookups and favorites.
## Requirements
### Requirement: External lookup entry points
The system SHALL accept a lookup request originating outside the search field — from a share action ("Look up in Aurelex"), an explicit lookup intent, or the clipboard — and SHALL open the article screen for that text as if it had been typed.

#### Scenario: Share text to Aurelex
- **WHEN** the user selects text in another app and shares it to Aurelex
- **THEN** the app opens and shows the article for that text

#### Scenario: Clipboard lookup
- **WHEN** the user chooses to look up the current clipboard text from the app
- **THEN** the app looks up and shows the article for that text

#### Scenario: Not-found from an external lookup
- **WHEN** the shared or clipboard text is not in any loaded dictionary
- **THEN** the app shows the standard "word not found" indication with a way back to search

### Requirement: Lookup history
The system SHALL record every successful article lookup and SHALL let the user browse recent lookups, re-look-up any of them, and remove individual items or clear the whole list. History SHALL persist across app restarts. Each history entry SHALL persist the dictionary group the lookup was produced in (0 = "All"); entries are deduplicated by (word, group), the newer one wins, and the list is capped at 500. Opening an entry SHALL restore that group (falling back to "All" if it no longer exists). The history browse surface SHALL be the Search pane's candidate area shown when the search field is empty (or when a typed query matches nothing); there SHALL be no dedicated History tab.

#### Scenario: Lookups are recorded
- **WHEN** the user successfully looks up a word
- **THEN** that word appears at the top of the history list together with the dictionary group used for the lookup

#### Scenario: Empty search shows history
- **WHEN** the user opens the Search tab with an empty search field
- **THEN** the candidate area lists recent lookups, most recent first, in place of suggestions

#### Scenario: Re-run a history item restores its group
- **WHEN** the user taps a word in the history list
- **THEN** the app switches to the group stored with that entry and shows the article for that word; if the stored group no longer exists, the app uses the "All" group

#### Scenario: Remove history items
- **WHEN** the user removes a history item (or clears all history)
- **THEN** the item (or all items) no longer appears in the history list, and the change survives a restart

#### Scenario: Duplicate (word, group) is coalesced
- **WHEN** the user looks up the same word in the same group more than once
- **THEN** only the most recent entry remains, at the top of the list

#### Scenario: Typing switches the surface to suggestions
- **WHEN** the user starts typing after history is shown
- **THEN** the candidate area switches to headword suggestions for the typed query

#### Scenario: Not-found lookups are not recorded
- **WHEN** the user looks up a word that is not in any dictionary
- **THEN** the failed lookup is not added to history

### Requirement: Favorites
The system SHALL let the user save the current article as a favorite, remove a saved favorite, and browse favorites with a tap to re-look-up. Favorites SHALL persist across app restarts. Each favorite SHALL persist the dictionary group of the article it was saved from; opening a favorite SHALL restore that group (falling back to "All" if it no longer exists).

#### Scenario: Save a favorite
- **WHEN** the user chooses to save the current article
- **THEN** the article's word appears in the favorites list together with the dictionary group used for the current article

#### Scenario: Remove a favorite
- **WHEN** the user removes an entry from favorites
- **THEN** it no longer appears in the favorites list, and the change survives a restart

#### Scenario: Open a favorite restores its group
- **WHEN** the user taps a word in the favorites list
- **THEN** the app switches to the group stored with that entry and shows the article for that word; if the stored group no longer exists, the app uses the "All" group

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

Which theme is in effect SHALL be derived from the theme mode and the system theme, and that single resolved theme SHALL drive every part of the app's appearance together: the app chrome and controls, the system status- and navigation-bar icon contrast, the theme dictionaries render articles in, and the article currently on screen. Switching modes SHALL take effect on the article already displayed without re-running the lookup, and a dictionary article SHALL be readable in both themes.

The background of the surface that shows an article — and of the headword-suggestion and recent-lookups pane that stands in for one — SHALL be the same color as the app's background, so that no seam is visible between the two. This SHALL hold in both themes, on the article's first painted frame as well as after the theme changes, and it SHALL hold whether or not the article's own content has finished loading.

#### Scenario: All appearance follows the resolved theme
- **WHEN** the resolved theme changes, whether because the mode changed or because the system theme did
- **THEN** the app chrome, the system bar icon contrast, the dictionary rendering theme, and the open article all change to that theme together

#### Scenario: The open article switches in place
- **WHEN** the resolved theme changes while an article is displayed
- **THEN** the displayed article changes to the new theme in place without losing the looked-up word or returning to an empty article

#### Scenario: Articles are readable in either theme
- **WHEN** an article is rendered in the light theme and again in the dark theme
- **THEN** the entry's text is legible against its background in both

#### Scenario: The article surface matches the app background
- **WHEN** an article, or the candidate pane shown in its place, is displayed in either theme
- **THEN** the surface behind the content is the same color as the surrounding app background, with no visible border or change of shade where the two meet

#### Scenario: The theme change carries the surface background
- **WHEN** the resolved theme changes while an article or the candidate pane is displayed
- **THEN** the surface's background becomes the new theme's background at the same moment as the rest of the app, without the previous theme's color being left behind

### Requirement: Recent lookups fill the candidate pane
The recent-lookups (history) surface SHALL fill the Search pane's candidate area from the top of that area down to the bottom navigation dock, rather than stopping partway, and the bottom dock SHALL remain visible. This full-height presentation SHALL apply to the history surface only: the headword-suggestion dropdown SHALL keep its bounded height.

#### Scenario: History fills the candidate area
- **WHEN** the search field is empty and the recent-lookups surface is shown
- **THEN** the list extends to the bottom of the candidate area, adjacent to the bottom navigation dock, and the dock stays visible

#### Scenario: A no-match query's history also fills the pane
- **WHEN** a typed query matches no headwords and the surface falls back to recent lookups
- **THEN** the history list fills the candidate area the same as on an empty field

#### Scenario: Suggestions keep their bounded dropdown
- **WHEN** the candidate surface is showing headword suggestions
- **THEN** it remains a bounded dropdown rather than filling the whole pane

### Requirement: Clipboard control reflects clipboard state
The Search pane's clipboard control SHALL be enabled only while the clipboard holds usable (non-whitespace) text, and SHALL be disabled while the clipboard is empty or holds only whitespace. Its enabled state SHALL track the clipboard while the app is running in the foreground, and SHALL be correct when the pane is first shown. When disabled, the control SHALL NOT paste or run a lookup. While it is enabled the control SHALL use the app's primary-action styling, so it does not read as a disabled control.

#### Scenario: Empty clipboard disables the control
- **WHEN** the clipboard is empty and the Search pane is shown
- **THEN** the clipboard control is disabled and tapping it does nothing

#### Scenario: Whitespace-only clipboard is treated as empty
- **WHEN** the clipboard contains only whitespace
- **THEN** the clipboard control is disabled

#### Scenario: Clipboard text enables the control
- **WHEN** the clipboard holds text
- **THEN** the clipboard control is enabled and tapping it pastes that text into the search field and looks it up

#### Scenario: A clipboard change updates the control live
- **WHEN** the clipboard becomes empty (or gains text) while the Search pane is on screen
- **THEN** the clipboard control's enabled state follows without leaving the pane

#### Scenario: Correct state on first show
- **WHEN** the user first switches to the Search pane
- **THEN** the clipboard control's enabled state already reflects the clipboard rather than a stale default

