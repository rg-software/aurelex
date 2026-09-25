## MODIFIED Requirements

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

### Requirement: Index build progress
The system SHALL show progress or a completion state while a full-text index is
being built, and the build SHALL NOT block the rest of the app: while indexing
runs, ordinary headword lookups and full-text searches over already-indexed
dictionaries SHALL be served without waiting for the build to finish, and other
operations (scanning, group edits, dictionary removal) SHALL proceed.

#### Scenario: Progress indication
- **WHEN** a dictionary is being full-text indexed
- **THEN** the app shows an in-progress state for that dictionary and the user can
  keep using the rest of the app

#### Scenario: Lookups and searches are served during a build
- **WHEN** a full-text index build is running
- **THEN** ordinary headword lookups and full-text searches over dictionaries that
  already have an index return results without waiting for the build to finish

#### Scenario: Large dictionary
- **WHEN** a very large dictionary is indexed
- **THEN** the app remains responsive, the build runs on a background service, and
  the index completes or the app reports why it could not

## ADDED Requirements

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
