# full-text-search Specification

## Purpose

Lets a user search the full article text of loaded dictionaries, not just
entry headwords, using an on-device indexed full-text search, and present
resulting headwords as tappable article lookups.

## Requirements

### Requirement: Full-text index
The system SHALL build a searchable full-text index for each imported dictionary
in app-private storage, using the dictionary's article bodies, SHALL maintain
that index so it reflects the loaded dictionary content, SHALL report
per-dictionary indexing state so the user knows what is available, and SHALL
delete the index when the dictionary is permanently removed. The system SHALL
build missing indexes automatically, in bulk, after dictionaries are imported,
without requiring a per-dictionary manual index action, and SHALL tolerate
dictionaries being added *while* a bulk build is already running — newly added
dictionaries are incorporated without restarting, without double-work, and
without falsely completing the overall progress. Automatic bulk indexing SHALL be
bounded: a dictionary large enough that building its index would dominate the
import chain SHALL NOT have its index built during that chain, and SHALL instead
have its index built when the user first runs a full-text search over it.

#### Scenario: Index build on demand
- **WHEN** the user loads a dictionary and initiates a full-text search on it
- **THEN** the app builds (or refreshes) that dictionary's full-text index before
  returning results

#### Scenario: Index state is visible
- **WHEN** the user opens the full-text search screen
- **THEN** each loaded dictionary shows whether its full-text index is built,
  missing, or being built

#### Scenario: Index respects content changes
- **WHEN** a dictionary is re-imported with changed source files
- **THEN** its full-text index is rebuilt rather than serving stale results

#### Scenario: Dictionary without FTS support
- **WHEN** a loaded dictionary does not support full-text indexing
- **THEN** the app documents it as not full-text-searchable and does not search it

#### Scenario: Automatic bulk indexing on add
- **WHEN** the user imports one or more dictionaries that lack a full-text index
- **THEN** the app builds their indexes automatically in bulk, with no
  per-dictionary manual Index action, and each dictionary becomes searchable as
  its index completes

#### Scenario: Very large dictionary is deferred, not auto-built during import
- **WHEN** an imported dictionary is large enough that building its full-text
  index would dominate the import chain
- **THEN** the import completes without building that dictionary's full-text
  index during the chain, and the index is built when the user first runs a
  full-text search over that dictionary

#### Scenario: Dictionary added while a bulk build is running
- **WHEN** the user imports a new dictionary while one or more other dictionaries
  are still being full-text indexed
- **THEN** the new dictionary is added to the batch, its index is built once the
  in-flight dictionaries finish, and the overall progress total grows to include
  it without restarting

#### Scenario: A dictionary is never indexed twice in one continuous run
- **WHEN** a dictionary is covered by two overlapping indexing requests (e.g.
  it is present at the start of a build and its folder is also re-imported
  mid-build)
- **THEN** the dictionary is indexed exactly once in that run and the batch
  completes without double work

#### Scenario: Index build survives app backgrounding
- **WHEN** a full-text index build for a large dictionary is still running and the
  app is moved to the background
- **THEN** the build continues on a background service rather than being cancelled,
  so the index still completes

#### Scenario: Removing a dictionary removes its index
- **WHEN** the user permanently removes an imported dictionary
- **THEN** the dictionary's full-text index is deleted along with its staged
  files, and it no longer appears in full-text search results

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
- **THEN** no search runs at that moment; the next submit runs the search in the newly selected group

#### Scenario: Changing the scope group clears the other group's results
- **WHEN** the user selects a different group in the scope control while results from a previous search are displayed
- **THEN** those results are cleared, so no result from the previous scope is shown as if it belonged to the new scope

#### Scenario: Toggling whole words does not start a search
- **WHEN** the user toggles the whole-words control
- **THEN** no search runs at that moment; the next submit runs the search with the new matching mode

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

#### Scenario: Search with wildcards
- **WHEN** the user enters a term ending in `*` (e.g. `read*`) with whole words off and submits it
- **THEN** the app matches all article-body terms sharing that prefix

### Requirement: Full-text search results
The system SHALL present full-text search results as a list of matching
headwords and SHALL let the user run a normal article lookup on any result, in
the FTS scope group, exactly like a typed headword lookup.

#### Scenario: Results lead to articles
- **WHEN** the user taps a full-text search result
- **THEN** the app shows that headword's article in the FTS scope group

#### Scenario: Result respects the FTS scope
- **WHEN** a full-text search is run with a specific FTS scope group
- **THEN** results come from that group's dictionaries and opens respect the group

#### Scenario: Search state survives navigation
- **WHEN** the user opens a result and comes back to the full-text search screen
- **THEN** the query and results remain available

### Requirement: Index build progress
The system SHALL show progress or a completion state while a full-text index is
being built, and the build SHALL NOT block the rest of the app: while indexing
runs, ordinary headword lookups and full-text searches over other dictionaries
SHALL be served without waiting more than one indexing slice for the build, and
other operations (scanning, group edits, dictionary removal) SHALL proceed. The
dictionary whose index is currently being built SHALL be withheld from lookups
and full-text search until its index completes.

#### Scenario: Progress indication
- **WHEN** a dictionary is being full-text indexed
- **THEN** the app shows an in-progress state for that dictionary and the user can
  keep using the rest of the app

#### Scenario: Lookups and searches are served during a build
- **WHEN** a full-text index build is running
- **THEN** ordinary headword lookups and full-text searches over other
  dictionaries return results within one indexing slice, while the dictionary
  being built is withheld until its index completes

#### Scenario: Large dictionary
- **WHEN** a very large dictionary is indexed
- **THEN** the app remains responsive, the build runs on a background service, and
  the index completes or the app reports why it could not

### Requirement: Interrupted index build resumes
The system SHALL persist incremental progress while building a full-text index, so
a build interrupted by app termination or a system kill resumes from its last
persisted point on a later run instead of re-indexing from the beginning, and a
build for a very large dictionary completes without exhausting device memory.

#### Scenario: Build interrupted then resumed
- **WHEN** a full-text index build is interrupted before finishing (e.g. the app
  process is killed) and the app is launched again
- **THEN** the build continues from its last persisted point instead of
  re-indexing articles that were already persisted

#### Scenario: Very large dictionary completes
- **WHEN** a very large dictionary is fully indexed
- **THEN** the build completes without the device running out of memory

### Requirement: Progress never falsely completes on concurrent add
The system SHALL NOT clear the "indexing in progress" indication for the overall
batch until every dictionary that was added to the batch (including ones added
while it ran) has been indexed or reported as failed.

#### Scenario: Early batch completion must not mask queued work
- **WHEN** an index build task finishes for the dictionaries known at its start,
  while additional dictionaries were added to the batch during the run
- **THEN** the build remains marked as in progress until the added dictionaries
  are also handled, and progress reflects the enlarged total

#### Scenario: Adding dictionaries in quick succession stages them all
- **WHEN** the user adds a second dictionary folder while the first folder's
  files are still being copied into app storage
- **THEN** the second folder is queued and is also copied/staged once the first
  copy completes, instead of being silently dropped
