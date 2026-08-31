## Purpose

Provides the core lookup experience on Android: searching headwords, rendering dictionary articles as HTML in a WebView, loading embedded resources, navigating between articles, and playing pronunciation audio.

## ADDED Requirements

### Requirement: Headword suggestions
The system SHALL offer headword suggestions as the user types, matching dictionary headwords by prefix and fuzzy (approximate) search.
Submitting a suggestion or the typed text SHALL trigger a full article lookup.

#### Scenario: Typing produces suggestions
- **WHEN** the user enters text in the search field
- **THEN** the app shows matching headword suggestions from the loaded dictionaries

#### Scenario: Selecting a suggestion looks up the article
- **WHEN** the user taps a suggestion
- **THEN** the app renders the combined article for that headword

### Requirement: Article rendering
The system SHALL render a lookup as HTML built from all loaded dictionaries that contain the headword, presented in the on-screen web view with the dictionaries ordered per the configured group.
Unknown words MUST NOT crash the app.

#### Scenario: Word found in multiple dictionaries
- **WHEN** the user looks up a headword present in several dictionaries
- **THEN** the article displays each dictionary's entry in the configured group order

#### Scenario: Word not found
- **WHEN** the user looks up a headword none of the dictionaries contain
- **THEN** the app shows a "not found" indication and offers a way to continue searching

### Requirement: Embedded dictionary resources
The system SHALL load resources referenced by an article (for example images and audio stored in mdict `.mdd` archives or referenced from dictionary folders) and display or play them within the article.

#### Scenario: Image in a dictionary archive renders
- **WHEN** an article references an image stored in an mdd archive
- **THEN** the image renders inside the article

#### Scenario: Missing resource does not break rendering
- **WHEN** an article references a resource that does not exist
- **THEN** the article still renders and the missing item is shown as broken or absent without error

### Requirement: In-article link navigation
The system SHALL open links within an article as in-app lookups of the linked word rather than leaving the app, and SHALL keep the user able to navigate back to the previous article.

#### Scenario: Tapping an article link
- **WHEN** the user taps a link inside an article
- **THEN** the app performs a lookup of the linked word within the app

#### Scenario: Back navigation
- **WHEN** the user navigates from one article to another via links
- **THEN** the app's back action returns to the previous article

### Requirement: Pronunciation audio
The system SHALL play pronunciation audio referenced by articles (ogg, mp3, wav) using an on-device player, triggered by audio links in the article.
Audio formats the player cannot decode (for example speex) MUST NOT crash the app and SHALL be gracefully indicated as unsupported.

#### Scenario: Playing an article audio link
- **WHEN** the user taps an audio control in an article whose format is supported
- **THEN** the app plays the pronunciation audio

#### Scenario: Unsupported audio format
- **WHEN** the user taps an audio control whose format the device cannot decode
- **THEN** the app does not play sound and signals that the format is unsupported