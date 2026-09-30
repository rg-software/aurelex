## MODIFIED Requirements

### Requirement: Full-text search query
The system SHALL let the user run a full-text search across the dictionaries of
the group selected in the full-text search pane's own scope control (independent
of the Search pane's active group), supporting at least the plain-text matching
mode, and must match dictionary articles whose body text contains the queried
term.

A search SHALL run only when the user submits it: by activating the pane's search
control, or by the keyboard's submit action on the query field. Entering or
editing text SHALL NOT run a search, changing the scope group SHALL NOT run a
search, and toggling the whole-words control SHALL NOT run a search — those
change what a later search will do, not whether one runs now.

Displayed results SHALL belong to the inputs that produced them. When any input
of the last search changes — its query text, its scope group, or its whole-words
mode — the displayed results SHALL be cleared, so the list on screen never
disagrees with the inputs the user can see. Leaving the pane and returning SHALL
NOT clear the results: they persist until an input changes or a new search is
submitted.

The pane SHALL provide a search control as an icon button. It SHALL be disabled
while the query is blank, and SHALL be disabled for the whole duration of a
submitted search, re-enabling when that search's results have landed (including
when they are empty or the search fails).

The pane SHALL offer a whole-words toggle that selects an exact-term matching
mode: with it on, a term SHALL match only that exact word and SHALL NOT be
expanded into prefix or approximate matches; with it off, a term SHALL match
terms that extend it (prefix matching). The two modes SHALL be distinct search
modes, not just a suffix difference, so a whole-words search for a short word
MUST NOT return longer words that merely resemble it.

<!--
Coverage note for the three scenarios below: `ui-polish` introduced them to
assert that the keyboard submit, a scope-group change, and the whole-words
toggle each *run* a search. This change abolishes the auto-triggers, so their
bodies now assert the opposite. The scenario *names* are retained because the
delta validator requires a MODIFIED block to carry every scenario name the
current spec has; the names are now misleading and are corrected in the main
spec when this change is archived.
-->

#### Scenario: Plain-text match
- **WHEN** the user enters a term present in an article body but not as a headword and submits it
- **THEN** the app returns that article's headword as a result

#### Scenario: Typing does not start a search
- **WHEN** the user types into the query field without submitting
- **THEN** no full-text search runs

#### Scenario: Editing the query clears results that no longer match it
- **WHEN** the query text differs from the text that produced the displayed results
- **THEN** the displayed results are cleared rather than left shown against the new query

#### Scenario: Changing the scope group does not start a search
- **WHEN** the user selects a different group in the scope control
- **THEN** no full-text search runs until the user submits

#### Scenario: Changing the scope group clears the other group's results
- **WHEN** the user selects a different group in the scope control while results from a previous search are displayed
- **THEN** those results are cleared, so no result from the previous scope is shown as if it belonged to the new scope

#### Scenario: Toggling whole words does not start a search
- **WHEN** the user toggles the whole-words control
- **THEN** no full-text search runs until the user submits, and the next submitted search uses the new mode

#### Scenario: Toggling whole words clears results from the other mode
- **WHEN** the user toggles the whole-words control while results from a previous search are displayed
- **THEN** those results are cleared, so results from one matching mode are not shown as if they came from the other

#### Scenario: Results survive a round trip to another pane
- **WHEN** the user opens a result, leaves the full-text search pane, and returns without changing any input
- **THEN** the query and its results are still displayed

#### Scenario: The search control submits the query
- **WHEN** the user activates the search control with a non-empty query
- **THEN** the app runs the full-text search for that query in the selected scope

#### Scenario: The search control is disabled while a search runs
- **WHEN** a submitted search is in flight
- **THEN** the search control is disabled, and it becomes enabled again once the results have landed

#### Scenario: The search control is disabled for a blank query
- **WHEN** the query field is empty or holds only whitespace
- **THEN** the search control is disabled

#### Scenario: A search that finds nothing still completes
- **WHEN** a submitted search returns no results
- **THEN** the app shows the empty-result indication and the search control is enabled again

#### Scenario: Whole words matches only the exact word
- **WHEN** the user submits a search with whole words on for a short word that is an indexed term
- **THEN** the results contain entries for that exact word and do not include longer words that merely share its beginning

#### Scenario: Whole words does not become a wildcard
- **WHEN** the user submits a search with whole words on for a term that is not an indexed word
- **THEN** the app reports no match for that exact word rather than expanding it to similar indexed terms

#### Scenario: Prefix matching when whole words is off
- **WHEN** the user submits a term that is a prefix of an indexed term with whole words off
- **THEN** the app matches the indexed terms sharing that prefix

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

#### Scenario: Submitting from the keyboard runs the search
- **WHEN** the user presses the keyboard's submit action with a non-empty query
- **THEN** the app runs a full-text search for that query in the selected scope — the keyboard submit is the same submit path as the search control

#### Scenario: Changing the scope group re-runs the search
- **WHEN** the user selects a different group in the scope control and then submits
- **THEN** the app runs the search in the newly selected group — the scope change alone runs nothing, but the next submit uses the new scope

#### Scenario: Toggling whole words re-runs the search
- **WHEN** the user toggles the whole-words control and then submits
- **THEN** the app runs the search with the new matching mode — the toggle alone runs nothing, but the next submit uses the new mode

#### Scenario: Search with wildcards
- **WHEN** the user enters a term ending in `*` (e.g. `read*`) with whole words off and submits it
- **THEN** the app matches all article-body terms sharing that prefix
