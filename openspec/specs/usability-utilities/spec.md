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
The system SHALL persist user preferences (favorites, history, the app dark-mode override, and the article zoom level) across app restarts.

#### Scenario: Preferences survive restart
- **WHEN** the user changes a preference (e.g. dark mode, article zoom) or modifies favorites/history and then restarts the app
- **THEN** the preferences and lists retain the user's changes

#### Scenario: Zoom level survives restart
- **WHEN** the user sets an article zoom level and restarts the app
- **THEN** articles render at the stored zoom level without the user re-setting it