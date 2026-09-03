# dictionary-management Specification

## Purpose

Lets a user load offline dictionaries onto an Android device by selecting a dictionary folder, and gives the app a stable, testable contract for which formats are supported and how index caches are built and refreshed on device.
## Requirements
### Requirement: Dictionary folder selection and scanning
The system SHALL let the user add dictionaries from folder-scoped (SAF) sources,
selected by the user from within allowed locations, and SHALL scan them for
supported dictionary files (mdict `.mdx`/`.mdd`, DSL `.dsl`/`.dsl.dz`, StarDict
`.ifo`). Added sources are scanned from app-private staging: the app copies the
source's supported dictionary files into app-private storage (reading them
through the SAF grant) and scans those copies there, because scoped storage
blocks direct path reads of the picked folders. The system SHALL NOT require
system-wide storage access to add dictionaries. Unsupported files in a scanned
location MUST NOT be treated as dictionaries.

#### Scenario: User selects a valid dictionary folder
- **WHEN** the user picks a folder containing mdict, DSL, or StarDict files
- **THEN** the app lists those dictionaries with their display names and source files

#### Scenario: Folder contains supported and unsupported formats
- **WHEN** the scanned folder contains supported files alongside files in other
  formats (bgl, aard, slob, etc.)
- **THEN** only the supported files are presented, and the others are ignored
  without error

#### Scenario: No supported dictionaries found
- **WHEN** the selected folder contains no supported dictionary files
- **THEN** the app tells the user that no supported dictionaries were found

#### Scenario: User selects a folder via the SAF picker
- **WHEN** the user taps Add dictionaries and selects a folder inside an allowed
  location
- **THEN** the app adds that folder as a dictionary source and scans it without
  requesting system-wide storage access

#### Scenario: Dictionary files are staged into app-private storage
- **WHEN** a source is added via the SAF picker
- **THEN** the app copies the source's supported dictionary files into
  app-private storage and scans those copies, so the dictionaries load regardless
  of where the source folder lives (device storage or a cloud provider)

#### Scenario: Dictionaries in nested subfolders load
- **WHEN** a source folder contains supported dictionary files in nested
  subfolders (e.g. the source root has language subfolders, each holding `.mdx`/
  `.dsl`/`.ifo` files)
- **THEN** the app loads those dictionaries too (scan covers subfolders
  recursively), so the whole picked location is searchable

#### Scenario: Removed a dictionary and re-scans the same source
- **WHEN** the user removes a dictionary and then re-scans its source
- **THEN** the dictionary is added back as a fresh entry (re-scan is not blocked
  by the earlier removal)

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
The system SHALL let the user organize loaded dictionaries into multiple named groups, each an ordered subset, and SHALL let the user select which group is active for lookups. An implicit "All" group containing every loaded dictionary is always available. Managing groups, their membership, and their order is part of this capability.

#### Scenario: All loaded dictionaries are the default group
- **WHEN** the user first loads dictionaries without creating any group
- **THEN** lookups use an implicit "All" group containing every loaded dictionary

#### Scenario: Create a group
- **WHEN** the user creates a named group and adds some dictionaries to it
- **THEN** the group appears in the groups list with that membership

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
The system SHALL let the user remove a loaded dictionary from the app's set of
dictionaries, and SHALL remove it consistently from lookups, groups, and
full-text search so no stale results reference it.

#### Scenario: Remove an individual dictionary
- **WHEN** the user removes one loaded dictionary
- **THEN** that dictionary's entry disappears from the dictionary list and future
  lookups no longer include it

#### Scenario: Removal is reflected in groups
- **WHEN** a removed dictionary was a member of the active group or any group
- **THEN** the group's membership no longer lists it, without error

#### Scenario: Removal is reflected in full-text search
- **WHEN** a removed dictionary had a full-text index
- **THEN** full-text search results no longer include matches from it

#### Scenario: Re-add after removal
- **WHEN** the user loads the same folder again after removing a dictionary from it
- **THEN** the dictionary is added back as a fresh entry (re-scan is not blocked
  by the earlier removal)

#### Scenario: Confirmation before removal
- **WHEN** the user triggers a dictionary removal
- **THEN** the app asks for confirmation before the dictionary is removed

