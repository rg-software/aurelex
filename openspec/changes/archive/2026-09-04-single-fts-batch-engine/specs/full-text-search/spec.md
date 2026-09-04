## MODIFIED Requirements

### Requirement: Automatic bulk indexing on add
The system SHALL build a searchable full-text index for each loaded dictionary
that supports it, automatically and in bulk, after dictionaries are added or
scanned, without requiring a per-dictionary manual index action. The bulk build
SHALL tolerate dictionaries being added *while a bulk build is already running*:
newly added dictionaries are incorporated into the running build without
restarting it, without indexing the same dictionary twice, and without falsely
completing the overall progress for dictionaries that are still queued.

#### Scenario: Dictionary added while a bulk build is running
- **WHEN** the user adds a new dictionary (folder) while one or more other
  dictionaries are still being full-text indexed
- **THEN** the new dictionary is added to the batch, its index is built once the
  in-flight dictionaries finish, and the "all dictionaries" progress total grows
  to include it without restarting from zero

#### Scenario: A dictionary is never indexed twice in one continuous run
- **WHEN** a dictionary is covered by two overlapping indexing requests (e.g.
  it is present at the start of a build and its folder is also re-added mid-build)
- **THEN** the dictionary is indexed exactly once in that run and the batch
  completes without double work

#### Scenario: The batch reports the current dictionary and overall progress
- **WHEN** dictionaries are added to a running bulk build
- **THEN** the progress indication keeps showing the dictionary currently being
  indexed (with its own progress) and an overall "N of M" that reflects the full
  set of dictionaries that will be indexed

## ADDED Requirements

### Requirement: Progress never falsely completes on concurrent add
The system SHALL NOT clear the "indexing in progress" indication for the
overall batch until every dictionary that was added to the batch (including
ones added while it ran) has been indexed or reported as failed.

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