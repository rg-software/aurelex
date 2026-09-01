## Purpose

Lets a user search the full article text of loaded dictionaries, not just
entry headwords, using an on-device indexed full-text search, and present
resulting headwords as tappable article lookups.

## ADDED Requirements

### Requirement: Full-text index
The system SHALL build a searchable full-text index for each loaded dictionary
that supports it, using the dictionary's article bodies, and SHALL maintain
that index so it reflects the loaded dictionary content. The system shall
report per-dictionary indexing state so the user knows what is available.

#### Scenario: Index build on demand
- **WHEN** the user loads a dictionary and initiates a full-text search on it
- **THEN** the app builds (or refreshes) that dictionary's full-text index before
  returning results

#### Scenario: Index state is visible
- **WHEN** the user opens the full-text search screen
- **THEN** each loaded dictionary shows whether its full-text index is built,
  missing, or being built

#### Scenario: Index respects content changes
- **WHEN** a dictionary's source files change or are rescanned
- **THEN** its full-text index is rebuilt rather than serving stale results

#### Scenario: Dictionary without FTS support
- **WHEN** a loaded dictionary does not support full-text indexing
- **THEN** the app documents it as not full-text-searchable and does not search it

### Requirement: Full-text search query
The system SHALL let the user run a full-text search across the active group's
dictionaries, supporting at least the plain-text matching mode, and must match
dictionary articles whose body text contains the queried term.

#### Scenario: Plain-text match
- **WHEN** the user enters a term present in an article body but not as a headword
- **THEN** the app returns that article's headword as a result

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

#### Scenario: Search modes
- **WHEN** the user switches between plain-text, wildcard, and regular-expression
  matching modes
- **THEN** the query is interpreted in that mode and results reflect the match

### Requirement: Full-text search results
The system SHALL present full-text search results as a list of matching
headwords and SHALL let the user run a normal article lookup on any result, in
the active group, exactly like a typed headword lookup.

#### Scenario: Results lead to articles
- **WHEN** the user taps a full-text search result
- **THEN** the app shows that headword's article in the active group

#### Scenario: Result respects the active group
- **WHEN** a full-text search is run in a specific group
- **THEN** results come from that group's dictionaries and opens respect the group

#### Scenario: Search state survives navigation
- **WHEN** the user opens a result and comes back to the full-text search screen
- **THEN** the query and results remain available

### Requirement: Index build progress
The system SHALL show progress or a completion state while a full-text index is
being built and shall not block the rest of the app while indexing runs.

#### Scenario: Progress indication
- **WHEN** a dictionary is being full-text indexed
- **THEN** the app shows an in-progress state for that dictionary and the user can
  keep using the rest of the app

#### Scenario: Large dictionary
- **WHEN** a very large dictionary is indexed
- **THEN** the app remains responsive and the index completes or the app reports
  why it could not