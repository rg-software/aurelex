# lookup Specification

## Purpose

Provides the core lookup experience on Android: searching headwords, rendering dictionary articles as HTML in a WebView, loading embedded resources, navigating between articles, and playing pronunciation audio.

## Requirements

### Requirement: Headword suggestions
The system SHALL offer headword suggestions as the user types, matching dictionary headwords by prefix and fuzzy (approximate) search.
Submitting a suggestion or the typed text SHALL trigger a full article lookup.
When the search field is empty, or when a typed query matches no dictionary headwords, the candidate surface SHALL show the recent lookup history instead of suggestions.

#### Scenario: Typing produces suggestions
- **WHEN** the user enters text in the search field
- **THEN** the app shows matching headword suggestions from the loaded dictionaries

#### Scenario: Selecting a suggestion looks up the article
- **WHEN** the user taps a suggestion
- **THEN** the app renders the combined article for that headword

#### Scenario: Empty search field shows history
- **WHEN** the search field is empty
- **THEN** the candidate surface shows the most recent lookup history instead of suggestions

#### Scenario: No matches falls back to history
- **WHEN** the user types a query that matches no dictionary headwords
- **THEN** the candidate surface reverts to showing the recent lookup history

### Requirement: Article rendering
The system SHALL render a lookup as HTML built from the dictionaries of the active group that contain the headword, presented in the on-screen web view with the dictionaries ordered per the active group, whether the lookup is initiated by typing in the search field, selecting a suggestion, or an external entry point (share action, clipboard, history, or favorites).
Successful article lookups SHALL be recorded in the lookup history.
Unknown words MUST NOT crash the app.

#### Scenario: Word found in multiple dictionaries
- **WHEN** the user looks up a headword present in several dictionaries of the active group
- **THEN** the article displays each dictionary's entry in the active group's order

#### Scenario: Word not found
- **WHEN** the user looks up a headword none of the active group's dictionaries contain
- **THEN** the app shows a "not found" indication and offers a way to continue searching

#### Scenario: Lookup from an external entry point
- **WHEN** the user initiates a lookup via a share action, the clipboard, history, or favorites
- **THEN** the article is rendered against the active group, and the word is added to the lookup history

#### Scenario: Lookup respects the active group
- **WHEN** a word is only present in dictionaries outside the active group
- **THEN** the lookup does not show that dictionary's entry (it is treated as not found for that group)

### Requirement: Embedded dictionary resources
The system SHALL load resources referenced by an article (for example images and audio stored in mdict `.mdd` archives or referenced from dictionary folders) and display or play them within the article.

#### Scenario: Image in a dictionary archive renders
- **WHEN** an article references an image stored in an mdd archive
- **THEN** the image renders inside the article

#### Scenario: Missing resource does not break rendering
- **WHEN** an article references a resource that does not exist
- **THEN** the article still renders and the missing item is shown as broken or absent without error

### Requirement: In-article link navigation
The system SHALL open links within an article as in-app lookups of the linked word rather than leaving the app, and SHALL keep the user able to navigate back to the previous article. Navigation between articles SHALL be browser-like: a back path through previously opened articles and a forward path through articles the user has backed out of, while a fresh lookup clears the forward path.

#### Scenario: Tapping an article link
- **WHEN** the user taps a link inside an article
- **THEN** the app performs a lookup of the linked word within the app

#### Scenario: Back navigation
- **WHEN** the user navigates from one article to another via links
- **THEN** the app's back action returns to the previous article

#### Scenario: Forward navigation
- **WHEN** the user has backed out of at least one article and chooses forward
- **THEN** the app re-opens the most recently backed-out article

#### Scenario: A fresh lookup clears forward history
- **WHEN** the user backs out of an article and then performs any fresh lookup (typed search, suggestion, history or favorites tap, or in-article link)
- **THEN** the forward path is cleared and the forward control is unavailable

### Requirement: Pronunciation audio
The system SHALL play pronunciation audio referenced by articles (ogg, mp3, wav) using an on-device player, triggered by audio links in the article.
Audio formats the player cannot decode (for example speex) MUST NOT crash the app and SHALL be gracefully indicated as unsupported.

#### Scenario: Playing an article audio link
- **WHEN** the user taps an audio control in an article whose format is supported
- **THEN** the app plays the pronunciation audio

#### Scenario: Unsupported audio format
- **WHEN** the user taps an audio control whose format the device cannot decode
- **THEN** the app does not play sound and signals that the format is unsupported
