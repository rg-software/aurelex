## MODIFIED Requirements

### Requirement: Remove a loaded dictionary
The system SHALL let the user permanently remove an imported dictionary from the
app, deleting its staged copy and its built indexes, and SHALL remove it
consistently from lookups, groups, and full-text search so no stale results
reference it. Removal SHALL be available at any time, including while the app is
staging, scanning, or full-text indexing: a removal issued during those phases
SHALL be applied without waiting for the chain to finish, and a removal issued
while a full-text index build for that dictionary is running SHALL cancel or drop
that build so the removed dictionary is neither left holding storage nor
reintroduced by the build, while other dictionaries' builds continue unaffected.

#### Scenario: Remove an individual dictionary
- **WHEN** the user removes one loaded dictionary
- **THEN** that dictionary's entry disappears from the dictionary list, its
  staged files and index are deleted from app storage, and future lookups no
  longer include it

#### Scenario: Removal is reflected in groups
- **WHEN** a removed dictionary was a member of the active group or any group
- **THEN** the group's membership no longer lists it, without error

#### Scenario: Removal is reflected in full-text search
- **WHEN** a removed dictionary had a full-text index
- **THEN** full-text search results no longer include matches from it, and the
  index is deleted

#### Scenario: Multi-select removal is immediate
- **WHEN** the user selects one or more dictionaries and taps Remove
- **THEN** the selected dictionaries are removed immediately, without a
  confirmation dialog, and their staged files and indexes are deleted

#### Scenario: Remove control is available during processing
- **WHEN** the app is staging, scanning, or full-text indexing dictionaries
- **THEN** the Dicts Remove control is enabled for the current selection instead
  of being disabled by the processing indication

#### Scenario: Remove while a full-text build is running
- **WHEN** the user removes a dictionary while its full-text index is being built
- **THEN** the dictionary is removed without waiting for the build to finish, its
  in-flight build is cancelled or dropped, its staged files and index are
  deleted, and any other dictionaries still being indexed continue unaffected

#### Scenario: Remove while staging or scanning
- **WHEN** the user removes a loaded dictionary while a newly picked folder is
  being staged or scanned
- **THEN** the removal is applied without waiting for the chain to finish and the
  newly imported dictionaries still load once the chain completes

#### Scenario: Re-add after removal
- **WHEN** the user imports the same folder again after removing a dictionary
  from it
- **THEN** the dictionary is imported again as a fresh entry (removal is not
  blocked)
