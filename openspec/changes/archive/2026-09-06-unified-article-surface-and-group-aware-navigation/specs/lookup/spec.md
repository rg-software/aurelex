## MODIFIED Requirements

### Requirement: Article rendering
The system SHALL render a lookup as HTML built from the dictionaries of the active group that contain the headword, presented in the on-screen web view with the dictionaries ordered per the active group, whether the lookup is initiated by typing in the search field, selecting a suggestion, or an external entry point (share action, clipboard, history, or favorites). Every article SHALL be presented in the Search tab's inline article surface; there SHALL NOT be a separate full-pane article view.
Successful article lookups SHALL be recorded in the lookup history.
Unknown words MUST NOT crash the app.

#### Scenario: Word found in multiple dictionaries
- **WHEN** the user looks up a headword present in several dictionaries of the active group
- **THEN** the article displays each dictionary's entry in the active group's order

#### Scenario: Word not found
- **WHEN** the user looks up a headword none of the active group's dictionaries contain
- **THEN** the app shows a "not found" indication and offers a way to continue searching

#### Scenario: Lookup from an external entry point opens inline
- **WHEN** the user initiates a lookup via a share action, the clipboard, history, favorites, or a full-text-search result
- **THEN** the article is rendered in the Search tab's inline article surface with the active group, the word is added to the lookup history, and it becomes part of the normal back/forward navigation

#### Scenario: Lookup from an external entry point
- **WHEN** the user initiates a lookup via a share action, the clipboard, history, or favorites
- **THEN** the article is rendered against the active group, and the word is added to the lookup history

#### Scenario: Lookup respects the active group
- **WHEN** a word is only present in dictionaries outside the active group
- **THEN** the lookup does not show that dictionary's entry (it is treated as not found for that group)

#### Scenario: Group with no dictionaries does not hang
- **WHEN** the user types a query while the active group has no dictionaries
- **THEN** suggestions are empty and returned promptly (no long stall), and a lookup in that group reports not-found rather than blocking

### Requirement: In-article link navigation
The system SHALL open links within an article as in-app lookups of the linked word rather than leaving the app, and SHALL keep the user able to navigate back to the previous article. Navigation between articles SHALL be browser-like: a back path through previously opened articles and a forward path through articles the user has backed out of; each stack entry SHALL carry the dictionary group the article was produced in, and returning/forwarding SHALL restore that group before re-rendering. A fresh lookup clears the forward path.

#### Scenario: Tapping an article link
- **WHEN** the user taps a link inside an article
- **THEN** the app performs a lookup of the linked word within the app, in the current active group

#### Scenario: Back navigation
- **WHEN** the user navigates from one article to another via links
- **THEN** the app's back action returns to the previous article and restores the dictionary group that produced it

#### Scenario: Forward navigation
- **WHEN** the user has backed out of at least one article and chooses forward
- **THEN** the app re-opens the most recently backed-out article and restores the dictionary group that produced it

#### Scenario: A fresh lookup clears forward history
- **WHEN** the user backs out of an article and then performs any fresh lookup (typed search, suggestion, history or favorites tap, or in-article link)
- **THEN** the forward path is cleared and the forward control is unavailable

### Requirement: Group-scope changes from the Search picker
When the active dictionary group is changed from the Search group picker: if the search field has text, the app SHALL perform an article lookup of that query in the newly selected group (setting it as the active group and recording the lookup in history); if the field is empty, the app SHALL set the group active and re-show the candidate surface (lookup history) without navigating.

#### Scenario: Changing group with a query triggers a lookup
- **WHEN** the user selects a different group in the Search group picker while a query is typed
- **THEN** the app looks up that query in the newly selected group, makes it the active group, and records the entry in lookup history

#### Scenario: Changing group with an empty field re-shows history
- **WHEN** the user selects a different group in the Search group picker while the search field is empty
- **THEN** the candidate surface re-shows the lookup history scoped to the newly selected group