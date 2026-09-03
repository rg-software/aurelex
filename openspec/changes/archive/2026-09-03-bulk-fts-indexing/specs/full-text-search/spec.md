## MODIFIED Requirements

### Requirement: Full-text index
The system SHALL build a searchable full-text index for each loaded dictionary
that supports it, using the dictionary's article bodies, and SHALL maintain
that index so it reflects the loaded dictionary content. The system shall
report per-dictionary indexing state so the user knows what is available.
The system SHALL build missing indexes automatically, in bulk, after
dictionaries are added or scanned, without requiring a per-dictionary manual
index action.

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

#### Scenario: Automatic bulk indexing on add
- **WHEN** the user adds one or more dictionaries that lack a full-text index
- **THEN** the app builds their indexes automatically in bulk, with no per-dictionary
  manual Index action, and each dictionary becomes searchable as its index completes

#### Scenario: Index build survives app backgrounding
- **WHEN** a full-text index build for a large dictionary is still running and the
  app is moved to the background
- **THEN** the build continues on a background service rather than being cancelled,
  so the index still completes

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
