# usability-utilities Specification

## Purpose

Adds everyday conveniences that make Aurelex useful as a daily dictionary: looking up words from other apps or the clipboard, browsing recent lookups and favorites, and pronouncing headwords with on-device text-to-speech.

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
The system SHALL record every successful article lookup and SHALL let the user browse recent lookups, re-look-up any of them, and remove individual items or clear the whole list. History SHALL persist across app restarts.

#### Scenario: Lookups are recorded
- **WHEN** the user successfully looks up a word
- **THEN** that word appears at the top of the history list

#### Scenario: Re-run a history item
- **WHEN** the user taps a word in the history list
- **THEN** the app shows the article for that word

#### Scenario: Remove history items
- **WHEN** the user removes a history item (or clears all history)
- **THEN** the item (or all items) no longer appears in the history list, and the change survives a restart

#### Scenario: Not-found lookups are not recorded
- **WHEN** the user looks up a word that is not in any dictionary
- **THEN** the failed lookup is not added to history

### Requirement: Favorites
The system SHALL let the user save the current article as a favorite, remove a saved favorite, and browse favorites with a tap to re-look-up. Favorites SHALL persist across app restarts.

#### Scenario: Save a favorite
- **WHEN** the user chooses to save the current article
- **THEN** the article's word appears in the favorites list

#### Scenario: Remove a favorite
- **WHEN** the user removes an entry from favorites
- **THEN** it no longer appears in the favorites list, and the change survives a restart

#### Scenario: Open a favorite
- **WHEN** the user taps a word in the favorites list
- **THEN** the app shows the article for that word

### Requirement: Text-to-speech pronunciation
The system SHALL pronounce a looked-up headword using the on-device text-to-speech engine when one is available, and SHALL degrade gracefully (no crash) when no engine is available or speech fails.

#### Scenario: Pronounce the headword
- **WHEN** the user chooses to pronounce the current article's word
- **THEN** the device speaks the word using its text-to-speech engine

#### Scenario: No TTS engine available
- **WHEN** the user chooses to pronounce a word but no text-to-speech engine is available
- **THEN** the app does not speak and indicates the feature is unavailable, without crashing

### Requirement: Settings persistence
The system SHALL persist user preferences (favorites, history, text-to-speech enabled, and the article dark-mode toggle) across app restarts.

#### Scenario: Preferences survive restart
- **WHEN** the user changes a preference (e.g. dark mode, TTS on/off) or modifies favorites/history and then restarts the app
- **THEN** the preferences and lists retain the user's changes