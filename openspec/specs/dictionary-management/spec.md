# dictionary-management Specification

## Purpose

Lets a user load offline dictionaries onto an Android device by selecting a dictionary folder, and gives the app a stable, testable contract for which formats are supported and how index caches are built and refreshed on device.
## Requirements
### Requirement: Dictionary folder selection and scanning
The system SHALL let the user add dictionaries by picking a folder through the
folder-scoped (SAF) picker and importing it: supported dictionary files (mdict
`.mdx`/`.mdd`, DSL `.dsl`/`.dsl.dz`, StarDict `.ifo`) are stage-copied into
app-private storage through the SAF grant and scanned there, because scoped
storage blocks direct path reads of the picked folders. The system SHALL NOT
require system-wide storage access to add dictionaries. Unsupported files in a
picked location MUST NOT be treated as dictionaries. There is no persistent
"source" abstraction: each pick is a one-off import and imported dictionaries
simply belong to the app's dictionary set until removed.

#### Scenario: User selects a valid dictionary folder
- **WHEN** the user picks a folder containing mdict, DSL, or StarDict files
- **THEN** the app imports (stages + scans) them and lists those dictionaries
  with display names

#### Scenario: Folder contains supported and unsupported formats
- **WHEN** the picked folder contains supported files alongside files in other
  formats (bgl, aard, slob, etc.)
- **THEN** only the supported files are imported, and the others are ignored
  without error

#### Scenario: No supported dictionaries found
- **WHEN** the selected folder contains no supported dictionary files
- **THEN** the app tells the user that no supported dictionaries were found and
  nothing is imported

#### Scenario: User selects a folder via the SAF picker
- **WHEN** the user taps Add dictionaries and selects a folder inside an allowed
  location
- **THEN** the app imports that folder's supported files as a one-off
  (stage-copy + scan) without requesting system-wide storage access

#### Scenario: Dictionary files are staged into app-private storage
- **WHEN** a folder is imported via the SAF picker
- **THEN** the app copies the folder's supported dictionary files into
  app-private storage and scans those copies, so the dictionaries load
  regardless of where the original folder lives (device storage or a cloud
  provider)

#### Scenario: Dictionaries in nested subfolders load
- **WHEN** a picked folder contains supported dictionary files in nested
  subfolders
- **THEN** the app imports those files too (staging covers subfolders
  recursively), so the whole picked location is searchable

#### Scenario: Removed a dictionary and re-scans the same source
- **WHEN** the user permanently removes a dictionary and then imports its folder
  again
- **THEN** the dictionary is added back as a fresh entry (removal is not blocked)

### Requirement: Index build and validation on device
The system SHALL build a lookup index for each loaded dictionary on the device when that dictionary's index does not yet exist or is out of date, and SHALL show the user the progress of the build.
Lookup MUST NOT return results for a dictionary until its index build has finished.

#### Scenario: First-time load triggers indexing
- **WHEN** the user loads a dictionary whose index has never been built
- **THEN** the app shows an indexing progress indication and does not offer results from that dictionary until indexing completes

#### Scenario: Index is up to date
- **WHEN** the user loads a dictionary whose index is already valid
- **THEN** the app skips indexing and makes that dictionary available immediately

#### Scenario: Index is out of date
- **WHEN** the underlying dictionary file has changed or the index format version differs from the engine's
- **THEN** the app rebuilds the index for that dictionary and informs the user that reindexing was needed

### Requirement: Dictionary groups
The system SHALL let the user organize loaded dictionaries into multiple named groups, each an ordered subset, and SHALL let the user select which group is active for lookups. An implicit "All" group containing every loaded dictionary is always available. Managing groups, their membership, their order, and the active group is part of this capability. Groups SHALL persist across app restarts (membership stored by stable dictionary identifier and re-resolved after dictionaries load).

#### Scenario: All loaded dictionaries are the default group
- **WHEN** the user first loads dictionaries without creating any group
- **THEN** lookups use an implicit "All" group containing every loaded dictionary

#### Scenario: Create a group
- **WHEN** the user creates a named group and adds some dictionaries to it
- **THEN** the group appears in the groups list with that membership

#### Scenario: Groups survive restart
- **WHEN** the user restarts the app after creating groups
- **THEN** the same named groups, membership, order, and active selection are restored

#### Scenario: Select the active group
- **WHEN** the user picks a group as active
- **THEN** subsequent lookups use only that group's dictionaries, in that group's order

#### Scenario: Reorder dictionaries within a group
- **WHEN** the user changes the order of dictionaries inside a group
- **THEN** the combined article for that group respects the new order

#### Scenario: Delete a group
- **WHEN** the user deletes a group
- **THEN** the group no longer appears in the list, and lookups fall back to the "All" group (or the next active group), without error

#### Scenario: Delete a group that is active
- **WHEN** the user deletes the currently active group
- **THEN** the app falls back to the "All" group so lookups keep working

### Requirement: Remove a loaded dictionary
The system SHALL let the user permanently remove an imported dictionary from the
app, deleting its staged copy and its built indexes, and SHALL remove it
consistently from lookups, groups, and full-text search so no stale results
reference it.

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

#### Scenario: Confirmation before removal
- **WHEN** the user triggers a dictionary removal
- **THEN** the app asks for confirmation before the dictionary is removed,
  stating that removal deletes the app's copy of the dictionary

#### Scenario: Re-add after removal
- **WHEN** the user imports the same folder again after removing a dictionary
  from it
- **THEN** the dictionary is imported again as a fresh entry (removal is not
  blocked)

### Requirement: Folder additions are serialized, never dropped
The system SHALL accept dictionary folder additions requested while a previous
folder's files are still being staged into app storage, queueing the pending
folder and processing it immediately after the current copy completes, instead
of discarding it.

#### Scenario: Second pick during an active stage copy
- **WHEN** the user picks a second dictionary folder while the first one is
  still being copied into app storage
- **THEN** the second folder is not lost: after the first copy finishes, the
  second is staged and its dictionaries are scanned and indexed

#### Scenario: A single pick that fails is surfaced
- **WHEN** staging a queued folder fails (e.g. the grant was revoked before the
  copy ran)
- **THEN** the app reports the failure and leaves the other dictionaries
  unaffected, without silently discarding the failed folder


### Requirement: Dictionary display metadata
The system SHALL show each dictionary in the Dicts list with its source/target
language pair and an approximate size, instead of its raw file path, so the
list is readable without exposing storage details. When a dictionary is still
being indexed and its size is not yet known, the size SHALL be omitted (shown
once known). When a source or target language is not known, it SHALL be shown
as `?`.

#### Scenario: Row shows language pair and size
- **WHEN** the user opens the Dicts tab
- **THEN** each dictionary row shows its name, then `Source/Target` and an
  approximate size (e.g. `English/Russian · 145 MB`), and never the file path

#### Scenario: Unknown language pair
- **WHEN** a dictionary's source or target language is not known
- **THEN** the unknown side is displayed as `?` (e.g. `English/? · 12 MB`)

#### Scenario: Size hidden while indexing
- **WHEN** a dictionary is still being full-text indexed and its size is unknown
- **THEN** the row shows the language pair without the size, and the size appears
  once indexing finishes and the size is known

### Requirement: By-Pair grouped dictionary list
The system SHALL let the user toggle a "By Pair" grouping on the Dicts tab. When
off, dictionaries are sorted alphabetically by name. When on, dictionaries are
grouped under color-highlighted caption rows, one per source/target language
pair, sorted alphabetically by pair; within each pair the dictionaries are
sorted alphabetically by name.

#### Scenario: Toggle off shows flat alphabetical list
- **WHEN** "By Pair" is off
- **THEN** dictionaries are listed in one flat list sorted alphabetically by name

#### Scenario: Toggle on groups by language pair
- **WHEN** "By Pair" is on
- **THEN** dictionaries are grouped under caption rows labeled by their
  source/target pair, pairs are sorted alphabetically, and dictionaries within a
  pair are sorted alphabetically by name

### Requirement: Batch and per-pair dictionary removal
The system SHALL let the user remove a whole language-pair group at once from a
pair caption row, and (as a lighter convenience) remove several selected
dictionaries at once via a "RemoveSelected" control. Both reuse the permanent
removal behaviour (staged files + indexes deleted).

#### Scenario: Remove a language pair
- **WHEN** the user taps Remove on a pair caption row
- **THEN** every dictionary having that source/target pair is permanently removed
  and disappears from the list, lookups, groups, and full-text search

#### Scenario: Multi-select and RemoveSelected
- **WHEN** the user taps dictionary rows to select them (at least one) and then
  taps RemoveSelected
- **THEN** all selected dictionaries are permanently removed and the selection is
  cleared

#### Scenario: RemoveSelected is disabled with no selection
- **WHEN** no dictionary rows are selected
- **THEN** the RemoveSelected button is disabled; it becomes enabled once at
  least one dictionary is selected
