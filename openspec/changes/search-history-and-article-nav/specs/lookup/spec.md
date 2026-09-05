## MODIFIED Requirements

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