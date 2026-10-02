## MODIFIED Requirements

### Requirement: Article rendering
The system SHALL render a lookup as HTML built from the dictionaries of the active group that contain the headword, presented in the on-screen web view with the dictionaries ordered per the active group, whether the lookup is initiated by typing in the search field, selecting a suggestion, or an external entry point (share action, clipboard, history, favorites, or full-text search). Every article SHALL be presented in the Search tab's inline article surface; there SHALL NOT be a separate full-pane article view.
Successful article lookups SHALL be recorded in the lookup history.
Unknown words, lookups scoped to a group with no dictionaries, and articles whose embedded resources load or fail concurrently MUST NOT crash or hang the app; navigation (switching tabs, opening other panes, and returning) SHALL remain responsive while an article is displayed.
Where the article is longer than the visible area, its text SHALL stay clear of the scrolling affordance: the scrollbar SHALL NOT be drawn over the entry text. The inset that keeps them apart SHALL be painted with the article's own background, so it reads as part of the article rather than as a separate strip.

#### Scenario: Word found in multiple dictionaries
- **WHEN** the user looks up a headword present in several dictionaries of the active group
- **THEN** the article displays each dictionary's entry in the active group's order

#### Scenario: Word not found
- **WHEN** the user looks up a headword none of the active group's dictionaries contain
- **THEN** the app shows a "not found" indication and offers a way to continue searching

#### Scenario: Lookup from an external entry point opens inline
- **WHEN** the user initiates a lookup via a share action, the clipboard, history, favorites, or a full-text-search result
- **THEN** the article is rendered in the Search tab's inline article surface with the active group, the word is added to the lookup history, and it becomes part of the normal back/forward navigation

#### Scenario: Lookup respects the active group
- **WHEN** a word is only present in dictionaries outside the active group
- **THEN** the lookup does not show that dictionary's entry (it is treated as not found for that group)

#### Scenario: Group with no dictionaries does not hang
- **WHEN** the user types a query while the active group has no dictionaries
- **THEN** suggestions are empty and returned promptly (no long stall), and a lookup in that group reports not-found rather than blocking

#### Scenario: Navigation stays responsive while an article with resources is shown
- **WHEN** an article whose entries reference embedded resources is displayed
- **THEN** switching to another tab and back completes without the app freezing or becoming unresponsive to input

#### Scenario: Scrolling a long article keeps the text clear of the scrollbar
- **WHEN** an article longer than the visible article area is scrolled
- **THEN** the scrollbar and the entry text do not overlap — the text ends before the edge the scrollbar occupies

#### Scenario: The reserved space is not visible as a gap
- **WHEN** an article is displayed, whether or not it is long enough to scroll
- **THEN** the space kept clear of the scrollbar is the same color as the article's background, so no strip or border is apparent
