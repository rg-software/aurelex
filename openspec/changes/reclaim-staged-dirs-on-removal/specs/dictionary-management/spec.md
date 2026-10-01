## MODIFIED Requirements

### Requirement: Remove a loaded dictionary
The system SHALL let the user permanently remove an imported dictionary from the
app, deleting its staged copy and its built indexes, and SHALL remove it
consistently from lookups, groups, and full-text search so no stale results
reference it.

Removal SHALL act on exactly the dictionary or dictionaries the user selected.
The identity of a removed dictionary MUST NOT depend on its position in the
displayed list: the list is sorted for presentation, and that order may differ
from the order the engine loaded the dictionaries in. Removing a multi-selection
SHALL remove each selected dictionary once, and only those dictionaries.

Deleting the staged copy SHALL mean the whole of it: the dictionary's primary
file, every companion file it was staged with, and any resource tree staged
alongside them. Removing a dictionary SHALL NOT leave files of that dictionary
in the staged location, and SHALL NOT leave its staged directory behind holding
those files. A staged directory that was emptied by the removal SHALL be
reclaimed, so removal neither retains the dictionary's storage nor leaves a
directory that no dictionary uses.

A staged directory SHALL NOT be reclaimed while any other loaded dictionary
still reads from it: one imported folder can hold several dictionaries, and
removing one MUST NOT delete a sibling's files. Equally, a staged directory
SHALL NOT be retained on behalf of a dictionary that has itself just been
removed.

The dictionary's indexes SHALL be deleted from the app's index directory - the
directory the engine writes them into, as the dictionary's identifier and its
`_FTS_*` companions - and no pre-fix index left beside that directory for the
same identifier SHALL survive the removal. Removing one dictionary SHALL leave
every other dictionary's indexes untouched. The effect on groups SHALL be
durable immediately, not only after the next scan.

Removal SHALL be available at any time, including while the app is staging,
scanning, or full-text indexing: a removal issued during those phases SHALL be
applied within a bounded time (at most one indexing slice, not the whole chain),
and a removal issued while a full-text index build for that dictionary is
running SHALL cancel or drop that build so the removed dictionary is neither
left holding storage nor reintroduced by the build, while other dictionaries'
builds continue unaffected.

#### Scenario: Remove an individual dictionary
- **WHEN** the user removes one loaded dictionary
- **THEN** that dictionary's entry disappears from the dictionary list, its
  staged files and its indexes are deleted, and it no longer contributes
  results to lookups, groups or full-text search

#### Scenario: All of the dictionary's staged files go, not only the primary one
- **WHEN** a dictionary staged with companion files and a resource tree is removed
- **THEN** its primary file, its companions and its resource tree are all
  deleted, so none of that dictionary's files remain in the staged location

#### Scenario: The emptied staged directory is reclaimed
- **WHEN** a dictionary is removed and no other loaded dictionary reads from its
  staged directory
- **THEN** that staged directory is removed rather than left behind, so the
  removal releases the storage the dictionary occupied

#### Scenario: A staged directory shared with a surviving dictionary is kept
- **WHEN** one imported folder holds several dictionaries and the user removes
  one of them
- **THEN** the staged directory survives and the dictionaries that were not
  removed still load and keep working

#### Scenario: The removed dictionary does not itself keep its directory alive
- **WHEN** a dictionary is removed and it was the only dictionary reading from
  its staged directory
- **THEN** the shared-directory guard does not treat the removed dictionary as a
  remaining user of that directory

#### Scenario: A leftover staged directory holding no dictionary is reclaimable
- **WHEN** a staged directory remains that holds no primary file any dictionary
  loads
- **THEN** it is reclaimed rather than accumulating, including one left behind by
  an earlier removal

#### Scenario: Removal targets the selected dictionary regardless of list order
- **WHEN** the user removes a dictionary whose position in the displayed list
  differs from its engine load order
- **THEN** the dictionary that is actually removed is the one selected

#### Scenario: Multi-select removal removes exactly the selection
- **WHEN** the user selects several dictionaries and removes them
- **THEN** exactly those dictionaries are removed, each once, and no other
  dictionary is affected

#### Scenario: The index inside the index directory is deleted
- **WHEN** a loaded dictionary is removed
- **THEN** its index, and the `_FTS_*` companions belonging to it, are deleted
  from the app's index directory

#### Scenario: A pre-fix index beside the index directory is also deleted
- **WHEN** a dictionary is removed whose index was built by a version that placed
  indexes beside the index directory rather than inside it
- **THEN** that stray index is deleted too, so no index for a removed dictionary
  survives

#### Scenario: Other dictionaries keep their indexes
- **WHEN** one dictionary is removed while others remain loaded
- **THEN** every remaining dictionary's index is still present and those
  dictionaries stay searchable

#### Scenario: Removal is reflected in groups
- **WHEN** a removed dictionary belonged to a group
- **THEN** it no longer appears in that group

#### Scenario: Removal's effect on groups survives a restart
- **WHEN** the user removes a dictionary that belonged to a group and then
  restarts the app
- **THEN** the dictionary is still absent from the group, and no stale
  membership referencing it is restored

#### Scenario: Removal is reflected in full-text search
- **WHEN** a dictionary is removed
- **THEN** full-text search no longer returns results from it

#### Scenario: Multi-select removal is immediate
- **WHEN** the user removes a multi-selection of dictionaries
- **THEN** all of them are removed in one action and the list reflects every
  removal without a further interaction

#### Scenario: Re-add after removal
- **WHEN** the user permanently removes a dictionary and then imports the same
  dictionary again
- **THEN** it is added back as a fresh entry with a working index

#### Scenario: Remove control is available during processing
- **WHEN** the app is staging, scanning, or building an index and the user
  removes a dictionary
- **THEN** the removal is applied within a bounded time rather than waiting for
  the whole chain to finish

#### Scenario: Remove while a full-text build is running
- **WHEN** a full-text index build is running for a dictionary and the user
  removes that dictionary
- **THEN** the build is cancelled or dropped, the dictionary is not reintroduced
  by it, and other dictionaries' builds continue unaffected

#### Scenario: Remove while staging or scanning
- **WHEN** the user removes a dictionary while a different import is being
  staged or scanned
- **THEN** the removal takes effect and the in-flight staging or scanning is not
  corrupted by it
