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
without falsely completing the overall progress.

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

#### Scenario: Search with wildcards
- **WHEN** the user enters a term ending in `*` (e.g. `read*`)
- **THEN** the app matches all article-body terms sharing that prefix, and a
  plain term (no wildcard) matches exactly

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
being built and shall not block the rest of the app while indexing runs.

#### Scenario: Progress indication
- **WHEN** a dictionary is being full-text indexed
- **THEN** the app shows an in-progress state for that dictionary and the user can
  keep using the rest of the app

#### Scenario: Large dictionary
- **WHEN** a very large dictionary is indexed
- **THEN** the app remains responsive, the build runs on a background service, and
  the index completes or the app reports why it could not

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
