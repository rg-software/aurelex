## MODIFIED Requirements

### Requirement: Full-text search query
The system SHALL let the user run a full-text search across the dictionaries of
the group selected in the full-text search pane's own scope control (independent
of the Search pane's active group), supporting at least the plain-text matching
mode, and must match dictionary articles whose body text contains the queried
term.

The full-text search pane SHALL NOT require a dedicated submit control. With a
non-empty query the search SHALL run when the user submits the query from the
keyboard, when the pane's scope group changes, and when the whole-words mode is
toggled, so the results always reflect the current query, scope, and matching
mode.

#### Scenario: Plain-text match
- **WHEN** the user enters a term present in an article body but not as a headword
- **THEN** the app returns that article's headword as a result

#### Scenario: Submitting from the keyboard runs the search
- **WHEN** the user presses the keyboard's submit action with a non-empty query
- **THEN** the app runs the full-text search for that query in the selected scope

#### Scenario: Changing the scope group re-runs the search
- **WHEN** the user selects a different group in the full-text search pane's scope control while a query is present
- **THEN** the app re-runs the search in the newly selected group

#### Scenario: Toggling whole words re-runs the search
- **WHEN** the user toggles the whole-words control while a query is present
- **THEN** the app re-runs the search with the new matching mode

#### Scenario: No matches
- **WHEN** no article body contains any of the query terms
- **THEN** the app shows an empty-result indication

#### Scenario: No index yet
- **WHEN** the user searches a dictionary whose full-text index has not been built
- **THEN** the app builds the index before returning results, or clearly explains
  why results are unavailable

#### Scenario: Empty or invalid query
- **WHEN** the user submits an empty or malformed query
- **THEN** the app reports the problem instead of crashing

#### Scenario: Search with wildcards
- **WHEN** the user enters a term ending in `*` (e.g. `read*`)
- **THEN** the app matches all article-body terms sharing that prefix, and a
  plain term (no wildcard) matches exactly
