## MODIFIED Requirements

### Requirement: Headword suggestions
The system SHALL offer headword suggestions as the user types, matching dictionary headwords by prefix and fuzzy (approximate) search.
Submitting a suggestion or the typed text SHALL trigger a full article lookup. A query submitted from the keyboard (the IME action) SHALL open the top (most relevant) suggestion when the query has suggestions, and SHALL look up the literal typed text when it has none.
When the search field is empty, or when a typed query matches no dictionary headwords, the candidate surface SHALL show the recent lookup history instead of suggestions.
A suggestion response SHALL NOT paint the candidate surface over an article that is being loaded, or has loaded, for the submitted query: an in-flight or completed article lookup takes precedence over suggestions for the same query.

#### Scenario: Typing produces suggestions
- **WHEN** the user enters text in the search field
- **THEN** the app shows matching headword suggestions from the loaded dictionaries

#### Scenario: Selecting a suggestion looks up the article
- **WHEN** the user taps a suggestion
- **THEN** the app renders the combined article for that headword

#### Scenario: Submitting from the keyboard opens the top suggestion
- **WHEN** the user presses the keyboard's submit action while the query has one or more suggestions
- **THEN** the app opens the article for the top (most relevant) suggestion, the same article tapping that suggestion would open

#### Scenario: Submitting from the keyboard with no suggestions looks up the typed text
- **WHEN** the user presses the keyboard's submit action while the query has no suggestions
- **THEN** the app looks up the literal typed text

#### Scenario: Empty search field shows history
- **WHEN** the search field is empty
- **THEN** the candidate surface shows the most recent lookup history instead of suggestions

#### Scenario: No matches falls back to history
- **WHEN** the user types a query that matches no dictionary headwords
- **THEN** the candidate surface reverts to showing the recent lookup history

#### Scenario: Switching group with a query triggers a lookup
- **WHEN** the user selects a different group in the Search group picker while the search field has text
- **THEN** the app performs an article lookup of that query in the newly selected group, makes it the active group, records the entry in lookup history, and shows the article without the suggestion list left covering it

#### Scenario: Switching group with an empty field re-shows history
- **WHEN** the user selects a different group in the Search group picker while the search field is empty
- **THEN** the app sets that group active and re-shows the lookup history scoped to it, without navigating

#### Scenario: A late suggestion response does not cover the article
- **WHEN** a suggestion query is still in flight when the article for the submitted text starts loading or finishes rendering
- **THEN** the article is what remains shown, and the arriving suggestions do not repaint over it
