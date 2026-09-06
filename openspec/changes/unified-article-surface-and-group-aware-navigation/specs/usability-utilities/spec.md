## MODIFIED Requirements

### Requirement: Lookup history
The system SHALL record every successful article lookup and SHALL let the user browse recent lookups, re-look-up any of them, and remove individual items or clear the whole list. History SHALL persist across app restarts. Each history entry SHALL persist the dictionary group that produced the lookup; tapping an entry SHALL restore that group (falling back to the default "All" group if it no longer exists) before rendering the article. The history browse surface SHALL be the Search pane's candidate area shown when the search field is empty (or when a typed query matches nothing); there SHALL be no dedicated History tab.

#### Scenario: Lookups are recorded
- **WHEN** the user successfully looks up a word
- **THEN** that word appears at the top of the history list together with the dictionary group used for the lookup

#### Scenario: Empty search shows history
- **WHEN** the user opens the Search tab with an empty search field
- **THEN** the candidate area lists recent lookups, most recent first, in place of suggestions

#### Scenario: Re-run a history item restores its group
- **WHEN** the user taps a word in the history list
- **THEN** the app switches to the group stored with that entry and shows the article for that word; if the stored group no longer exists, the app uses the "All" group

#### Scenario: Re-run a history item
- **WHEN** the user taps a word in the history list
- **THEN** the app shows the article for that word

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

#### Scenario: Legacy history without groups loads as All
- **WHEN** a history file created before groups were stored is loaded
- **THEN** every entry without a stored group is treated as produced by the "All" group

### Requirement: Favorites
The system SHALL let the user save the current article as a favorite, remove a saved favorite, and browse favorites with a tap to re-look-up. Favorites SHALL persist across app restarts. Each favorite SHALL persist the dictionary group that produced the article; tapping a favorite SHALL restore that group (falling back to the "All" group if it no longer exists) before rendering the article.

#### Scenario: Save a favorite
- **WHEN** the user chooses to save the current article
- **THEN** the article's word appears in the favorites list together with the dictionary group used for the current article

#### Scenario: Remove a favorite
- **WHEN** the user removes an entry from favorites
- **THEN** it no longer appears in the favorites list, and the change survives a restart

#### Scenario: Open a favorite restores its group
- **WHEN** the user taps a word in the favorites list
- **THEN** the app switches to the group stored with that entry and shows the article for that word; if the stored group no longer exists, the app uses the "All" group

#### Scenario: Open a favorite
- **WHEN** the user taps a word in the favorites list
- **THEN** the app shows the article for that word

#### Scenario: Legacy favorites without groups load as All
- **WHEN** a favorites file created before groups were stored is loaded
- **THEN** every entry without a stored group is treated as produced by the "All" group