## MODIFIED Requirements

### Requirement: Full-text index
The system SHALL build a searchable full-text index for each imported dictionary
in app-private storage, maintain it to reflect the dictionary's content, and
delete it when the dictionary is permanently removed. The system SHALL build
missing indexes automatically, in bulk, after dictionaries are imported, without
requiring a per-dictionary manual index action.

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