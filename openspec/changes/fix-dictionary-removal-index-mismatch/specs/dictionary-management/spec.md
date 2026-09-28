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

The dictionary's indexes SHALL be deleted from the app's index directory - the
directory the engine writes them into, as the dictionary's identifier and its
`_FTS_*` companions - and no pre-fix index left beside that directory for the
same identifier SHALL survive the removal. Removing one dictionary SHALL leave
every other dictionary's indexes untouched. The effect on groups SHALL be
durable immediately, not only after the next scan.

#### Scenario: Remove an individual dictionary
- **WHEN** the user removes one loaded dictionary
- **THEN** that dictionary's entry disappears from the dictionary list, its
  staged files and index are deleted from app storage, and future lookups no
  longer include it

#### Scenario: Removal targets the selected dictionary regardless of list order
- **WHEN** the user removes a dictionary whose position in the displayed
  (alphabetically sorted) list does not match the order it was loaded in
- **THEN** the dictionary the user selected is the one removed, and no other
  loaded dictionary is unloaded or deleted

#### Scenario: Multi-select removal removes exactly the selection
- **WHEN** the user removes several selected dictionaries at once
- **THEN** every selected dictionary is removed and no unselected dictionary is
  removed, regardless of the order the removals are applied in

#### Scenario: The index inside the index directory is deleted
- **WHEN** a dictionary with a built index is removed
- **THEN** the identifier's index entry and its full-text index directory inside
  the app's index directory are both deleted, so the removal frees the space the
  index occupied

#### Scenario: A pre-fix index beside the index directory is also deleted
- **WHEN** a dictionary is removed on a device whose index still sits beside the
  index directory in the pre-fix layout
- **THEN** that entry and its full-text companion are deleted too, so the removal
  is correct regardless of whether the layout migration has run

#### Scenario: Other dictionaries keep their indexes
- **WHEN** one of several loaded dictionaries is removed
- **THEN** every other dictionary's index and full-text index remain in place and
  those dictionaries keep working

#### Scenario: Removal is reflected in groups
- **WHEN** a removed dictionary was a member of the active group or any group
- **THEN** the group's membership no longer lists it, without error

#### Scenario: Removal's effect on groups survives a restart
- **WHEN** the user removes a dictionary that belonged to a group and then
  restarts the app without any further scan or group edit
- **THEN** the group still does not list the removed dictionary

#### Scenario: Removal is reflected in full-text search
- **WHEN** a removed dictionary had a full-text index
- **THEN** full-text search results no longer include matches from it, and the
  index is deleted

#### Scenario: Multi-select removal is immediate
- **WHEN** the user selects one or more dictionaries and taps Remove
- **THEN** the selected dictionaries are removed immediately, without a
  confirmation dialog, and their staged files and indexes are deleted

#### Scenario: Re-add after removal
- **WHEN** the user imports the same folder again after removing a dictionary
  from it
- **THEN** the dictionary is imported again as a fresh entry (removal is not
  blocked), and its index is built anew rather than inherited from the removal
