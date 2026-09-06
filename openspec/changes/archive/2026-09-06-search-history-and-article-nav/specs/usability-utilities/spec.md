## MODIFIED Requirements

### Requirement: Lookup history
The system SHALL record every successful article lookup and SHALL let the user browse recent lookups, re-look-up any of them, and remove individual items or clear the whole list. History SHALL persist across app restarts. The history browse surface SHALL be the Search pane's candidate area shown when the search field is empty (or when a typed query matches nothing); there SHALL be no dedicated History tab.

#### Scenario: Lookups are recorded
- **WHEN** the user successfully looks up a word
- **THEN** that word appears at the top of the history list

#### Scenario: Empty search shows history
- **WHEN** the user opens the Search tab with an empty search field
- **THEN** the candidate area lists recent lookups, most recent first, in place of suggestions

#### Scenario: Re-run a history item
- **WHEN** the user taps a word in the history list
- **THEN** the app shows the article for that word

#### Scenario: Remove history items
- **WHEN** the user removes a history item (or clears all history)
- **THEN** the item (or all items) no longer appears in the history list, and the change survives a restart

#### Scenario: Typing switches the surface to suggestions
- **WHEN** the user starts typing after history is shown
- **THEN** the candidate area switches to headword suggestions for the typed query

#### Scenario: Not-found lookups are not recorded
- **WHEN** the user looks up a word that is not in any dictionary
- **THEN** the failed lookup is not added to history